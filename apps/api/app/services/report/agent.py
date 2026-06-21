"""ReportAgent：基于 图谱工具、ReACT 模式生成模拟报告 + 与用户对话。

拆分自原 report_agent.py（含 Prompt 模板常量）。
依赖：domain/report（领域）、report/logs（日志器）、report/manager（持久化编排）、
graph_tools（检索工具）、llm_client（LLM 调用）。
"""

import json
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from ...core.logger import get_logger
from ...domain.report import Report, ReportOutline, ReportSection, ReportStatus
from ...utils.llm_client import LLMClient
from ...utils.locale import get_language_instruction, t
from ..graph_tools import GraphToolsService
from . import react_parser, section_writer, tool_registry
from .logs import ReportConsoleLogger, ReportLogger
from .manager import ReportManager
from .prompts import (
    CHAT_OBSERVATION_SUFFIX,
    CHAT_SYSTEM_PROMPT_TEMPLATE,
    PLAN_SYSTEM_PROMPT,
    PLAN_USER_PROMPT_TEMPLATE,
)

logger = get_logger("superfish.report_agent")


# ═══════════════════════════════════════════════════════════════
# ReportAgent 主类
# ═══════════════════════════════════════════════════════════════


class ReportAgent:
    """
    Report Agent - 模拟报告生成Agent

    采用ReACT（Reasoning + Acting）模式：
    1. 规划阶段：分析模拟需求，规划报告目录结构
    2. 生成阶段：逐章节生成内容，每章节可多次调用工具获取信息
    3. 反思阶段：检查内容完整性和准确性
    """

    # 最大工具调用次数（每个章节）
    MAX_TOOL_CALLS_PER_SECTION = 5

    # 最大反思轮数
    MAX_REFLECTION_ROUNDS = 3

    # 对话中的最大工具调用次数
    MAX_TOOL_CALLS_PER_CHAT = 2

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: LLMClient | None = None,
        graph_tools: GraphToolsService | None = None,
    ):
        """
        初始化Report Agent

        Args:
            graph_id: 图谱ID
            simulation_id: 模拟ID
            simulation_requirement: 模拟需求描述
            llm_client: LLM客户端（可选）
            graph_tools: 图谱工具服务（可选）
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement

        self.llm = llm_client or LLMClient()
        self.graph_tools = graph_tools or GraphToolsService()

        # 工具定义
        self.tools = self._define_tools()

        # 日志记录器（在 generate_report 中初始化）
        self.report_logger: ReportLogger | None = None
        # 控制台日志记录器（在 generate_report 中初始化）
        self.console_logger: ReportConsoleLogger | None = None

        logger.info(t("report.agentInitDone", graphId=graph_id, simulationId=simulation_id))

    def _define_tools(self) -> dict[str, dict[str, Any]]:
        """定义可用工具（薄委托 tool_registry）。"""
        return tool_registry.define_tools()

    def _execute_tool(
        self, tool_name: str, parameters: dict[str, Any], report_context: str = ""
    ) -> str:
        """执行工具调用（薄委托 tool_registry.execute_tool，注入图谱工具与运行上下文）。"""
        return tool_registry.execute_tool(
            self.graph_tools,
            graph_id=self.graph_id,
            simulation_id=self.simulation_id,
            simulation_requirement=self.simulation_requirement,
            tool_name=tool_name,
            parameters=parameters,
            report_context=report_context,
        )

    # 合法的工具名称集合，用于裸 JSON 兜底解析时校验
    VALID_TOOL_NAMES = tool_registry.VALID_TOOL_NAMES

    def _parse_tool_calls(self, response: str) -> list[dict[str, Any]]:
        """从 LLM 响应解析工具调用（薄委托 react_parser，传入合法工具名集合）。"""
        return react_parser.parse_tool_calls(response, self.VALID_TOOL_NAMES)

    def _is_valid_tool_call(self, data: dict) -> bool:
        """校验并规范化工具调用 JSON（薄委托 react_parser）。"""
        return react_parser.is_valid_tool_call(data, self.VALID_TOOL_NAMES)

    def _get_tools_description(self) -> str:
        """生成工具描述文本（薄委托 tool_registry）。"""
        return tool_registry.tools_description(self.tools)

    def plan_outline(self, progress_callback: Callable | None = None) -> ReportOutline:
        """
        规划报告大纲

        使用LLM分析模拟需求，规划报告的目录结构

        Args:
            progress_callback: 进度回调函数

        Returns:
            ReportOutline: 报告大纲
        """
        logger.info(t("report.startPlanningOutline"))

        if progress_callback:
            progress_callback("planning", 0, t("progress.analyzingRequirements"))

        # 首先获取模拟上下文
        context = self.graph_tools.get_simulation_context(
            graph_id=self.graph_id, simulation_requirement=self.simulation_requirement
        )

        if progress_callback:
            progress_callback("planning", 30, t("progress.generatingOutline"))

        system_prompt = f"{PLAN_SYSTEM_PROMPT}\n\n{get_language_instruction()}"
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get("graph_statistics", {}).get("total_nodes", 0),
            total_edges=context.get("graph_statistics", {}).get("total_edges", 0),
            entity_types=list(context.get("graph_statistics", {}).get("entity_types", {}).keys()),
            total_entities=context.get("total_entities", 0),
            related_facts_json=json.dumps(
                context.get("related_facts", [])[:10], ensure_ascii=False, indent=2
            ),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )

            if progress_callback:
                progress_callback("planning", 80, t("progress.parsingOutline"))

            # 解析大纲
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(title=section_data.get("title", ""), content=""))

            outline = ReportOutline(
                title=response.get("title", "模拟分析报告"),
                summary=response.get("summary", ""),
                sections=sections,
            )

            if progress_callback:
                progress_callback("planning", 100, t("progress.outlinePlanComplete"))

            logger.info(t("report.outlinePlanDone", count=len(sections)))
            return outline

        except Exception as e:
            logger.error(t("report.outlinePlanFailed", error=str(e)))
            # 返回默认大纲（3个章节，作为fallback）
            return ReportOutline(
                title="未来预测报告",
                summary="基于模拟预测的未来趋势与风险分析",
                sections=[
                    ReportSection(title="预测场景与核心发现"),
                    ReportSection(title="人群行为预测分析"),
                    ReportSection(title="趋势展望与风险提示"),
                ],
            )

    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: list[str],
        progress_callback: Callable | None = None,
        section_index: int = 0,
    ) -> str:
        """用 ReACT 模式生成单个章节内容（薄委托 section_writer，以 self 作协作者）。"""
        return section_writer.generate_section_react(
            self,
            section,
            outline,
            previous_sections,
            progress_callback=progress_callback,
            section_index=section_index,
        )

    def generate_report(
        self,
        progress_callback: Callable[[str, int, str], None] | None = None,
        report_id: str | None = None,
    ) -> Report:
        """
        生成完整报告（分章节实时输出）

        每个章节生成完成后立即写入 Postgres（reports 表的 sections 字段），
        前端可轮询 /sections 实时获取，不需要等待整个报告完成。
        元数据/大纲/进度/章节/完整 markdown 均存于 Postgres；生成期的
        agent_log.jsonl / console_log.txt 仍写在运行节点本地。

        Args:
            progress_callback: 进度回调函数 (stage, progress, message)
            report_id: 报告ID（可选，如果不传则自动生成）

        Returns:
            Report: 完整报告
        """
        import uuid

        # 如果没有传入 report_id，则自动生成
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat(),
        )

        # 已完成的章节标题列表（用于进度追踪）
        completed_section_titles = []

        try:
            # 初始化：创建报告文件夹并保存初始状态
            ReportManager._ensure_report_folder(report_id)

            # 初始化日志记录器（结构化日志 agent_log.jsonl）
            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement,
            )

            # 初始化控制台日志记录器（console_log.txt）
            self.console_logger = ReportConsoleLogger(report_id)

            ReportManager.update_progress(
                report_id, "pending", 0, t("progress.initReport"), completed_sections=[]
            )
            ReportManager.save_report(report)

            # 阶段1: 规划大纲
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, t("progress.startPlanningOutline"), completed_sections=[]
            )

            # 记录规划开始日志
            self.report_logger.log_planning_start()

            if progress_callback:
                progress_callback("planning", 0, t("progress.startPlanningOutline"))

            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg: (
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
                )
            )
            report.outline = outline

            # 记录规划完成日志
            self.report_logger.log_planning_complete(outline.to_dict())

            # 保存大纲到文件
            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id,
                "planning",
                15,
                t("progress.outlineDone", count=len(outline.sections)),
                completed_sections=[],
            )
            ReportManager.save_report(report)

            logger.info(t("report.outlineSavedToFile", reportId=report_id))

            # 阶段2: 逐章节生成（分章节保存）
            report.status = ReportStatus.GENERATING

            total_sections = len(outline.sections)
            generated_sections = []  # 保存内容用于上下文

            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)

                # 更新进度
                ReportManager.update_progress(
                    report_id,
                    "generating",
                    base_progress,
                    t(
                        "progress.generatingSection",
                        title=section.title,
                        current=section_num,
                        total=total_sections,
                    ),
                    current_section=section.title,
                    completed_sections=completed_section_titles,
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        t(
                            "progress.generatingSection",
                            title=section.title,
                            current=section_num,
                            total=total_sections,
                        ),
                    )

                # 生成主章节内容
                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg, bp=base_progress: (
                        progress_callback(stage, bp + int(prog * 0.7 / total_sections), msg)
                        if progress_callback
                        else None
                    ),
                    section_index=section_num,
                )

                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                # 保存章节
                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                # 记录章节完成日志
                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip(),
                    )

                logger.info(
                    t("report.sectionSaved", reportId=report_id, sectionNum=f"{section_num:02d}")
                )

                # 更新进度
                ReportManager.update_progress(
                    report_id,
                    "generating",
                    base_progress + int(70 / total_sections),
                    t("progress.sectionDone", title=section.title),
                    current_section=None,
                    completed_sections=completed_section_titles,
                )

            # 阶段3: 组装完整报告
            if progress_callback:
                progress_callback("generating", 95, t("progress.assemblingReport"))

            ReportManager.update_progress(
                report_id,
                "generating",
                95,
                t("progress.assemblingReport"),
                completed_sections=completed_section_titles,
            )

            # 使用ReportManager组装完整报告
            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()

            # 计算总耗时
            total_time_seconds = (datetime.now() - start_time).total_seconds()

            # 记录报告完成日志
            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections, total_time_seconds=total_time_seconds
                )

            # 保存最终报告
            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id,
                "completed",
                100,
                t("progress.reportComplete"),
                completed_sections=completed_section_titles,
            )

            if progress_callback:
                progress_callback("completed", 100, t("progress.reportComplete"))

            logger.info(t("report.reportGenDone", reportId=report_id))

            # 关闭控制台日志记录器
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

        except Exception as e:
            logger.error(t("report.reportGenFailed", error=str(e)))
            report.status = ReportStatus.FAILED
            report.error = str(e)

            # 记录错误日志
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")

            # 保存失败状态
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id,
                    "failed",
                    -1,
                    t("progress.reportFailed", error=str(e)),
                    completed_sections=completed_section_titles,
                )
            except Exception:
                pass  # 忽略保存失败的错误

            # 关闭控制台日志记录器
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

    def chat(self, message: str, chat_history: list[dict[str, str]] = None) -> dict[str, Any]:
        """
        与Report Agent对话

        在对话中Agent可以自主调用检索工具来回答问题

        Args:
            message: 用户消息
            chat_history: 对话历史

        Returns:
            {
                "response": "Agent回复",
                "tool_calls": [调用的工具列表],
                "sources": [信息来源]
            }
        """
        logger.info(t("report.agentChat", message=message[:50]))

        chat_history = chat_history or []

        # 获取已生成的报告内容
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                # 限制报告长度，避免上下文过长
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [报告内容已截断] ..."
        except Exception as e:
            logger.warning(t("report.fetchReportFailed", error=e))

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "（暂无报告）",
            tools_description=self._get_tools_description(),
        )
        system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

        # 构建消息
        messages = [{"role": "system", "content": system_prompt}]

        # 添加历史对话
        for h in chat_history[-10:]:  # 限制历史长度
            messages.append(h)

        # 添加用户消息
        messages.append({"role": "user", "content": message})

        # ReACT循环（简化版）
        tool_calls_made = []
        max_iterations = 2  # 减少迭代轮数

        for iteration in range(max_iterations):
            response = self.llm.chat(messages=messages, temperature=0.5)

            # 解析工具调用
            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                # 没有工具调用，直接返回响应
                clean_response = re.sub(
                    r"<tool_call>.*?</tool_call>", "", response, flags=re.DOTALL
                )
                clean_response = re.sub(r"\[TOOL_CALL\].*?\)", "", clean_response)

                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [
                        tc.get("parameters", {}).get("query", "") for tc in tool_calls_made
                    ],
                }

            # 执行工具调用（限制数量）
            tool_results = []
            for call in tool_calls[:1]:  # 每轮最多执行1次工具调用
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append(
                    {
                        "tool": call["name"],
                        "result": result[:1500],  # 限制结果长度
                    }
                )
                tool_calls_made.append(call)

            # 将结果添加到消息
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']}结果]\n{r['result']}" for r in tool_results])
            messages.append({"role": "user", "content": observation + CHAT_OBSERVATION_SUFFIX})

        # 达到最大迭代，获取最终响应
        final_response = self.llm.chat(messages=messages, temperature=0.5)

        # 清理响应
        clean_response = re.sub(r"<tool_call>.*?</tool_call>", "", final_response, flags=re.DOTALL)
        clean_response = re.sub(r"\[TOOL_CALL\].*?\)", "", clean_response)

        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made],
        }
