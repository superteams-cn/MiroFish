"""ReACT 章节生成循环：逐章节驱动 LLM「思考→调用工具→观察」直至产出正文。

从 ReportAgent 抽出。循环需编排 agent 的多项行为（LLM 调用 / 工具解析与执行 / 工具描述 /
日志器），故以 ``agent`` 作为协作者回调，ReportAgent 以薄委托 ``_generate_section_react``
调用本函数。行为由 tests/test_report_section_writer.py（脚本化假 LLM）守护。
"""

from collections.abc import Callable

from ...core.logger import get_logger
from ...core.settings import settings
from ...domain.report import ReportOutline, ReportSection
from ...utils.locale import get_language_instruction, t
from .prompts import (
    REACT_FORCE_FINAL_MSG,
    REACT_INSUFFICIENT_TOOLS_MSG,
    REACT_INSUFFICIENT_TOOLS_MSG_ALT,
    REACT_OBSERVATION_TEMPLATE,
    REACT_TOOL_LIMIT_MSG,
    REACT_UNUSED_TOOLS_HINT,
    SECTION_SYSTEM_PROMPT_TEMPLATE,
    SECTION_USER_PROMPT_TEMPLATE,
)

logger = get_logger("superfish.report.section_writer")


def generate_section_react(
    agent,
    section: ReportSection,
    outline: ReportOutline,
    previous_sections: list[str],
    progress_callback: Callable | None = None,
    section_index: int = 0,
) -> str:
    """用 ReACT 模式生成单个章节内容（思考→工具→观察→… → Final Answer）。

    Args:
        agent: ReportAgent 协作者，提供 llm / 工具执行与解析 / 工具描述 / 日志器 / 配置。
        section: 要生成的章节；outline: 完整大纲；previous_sections: 已完成章节内容（保持连贯）。
        progress_callback: 进度回调；section_index: 章节索引（日志用）。
    """
    logger.info(t("report.reactGenerateSection", title=section.title))

    # 记录章节开始日志
    if agent.report_logger:
        agent.report_logger.log_section_start(section.title, section_index)

    system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
        report_title=outline.title,
        report_summary=outline.summary,
        simulation_requirement=agent.simulation_requirement,
        section_title=section.title,
        tools_description=agent._get_tools_description(),
    )
    system_prompt = f"{system_prompt}\n\n{get_language_instruction()}"

    # 构建用户prompt - 每个已完成章节各传入最大4000字
    if previous_sections:
        previous_parts = []
        for sec in previous_sections:
            # 每个章节最多4000字
            truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
            previous_parts.append(truncated)
        previous_content = "\n\n---\n\n".join(previous_parts)
    else:
        previous_content = "（这是第一个章节）"

    user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
        previous_content=previous_content,
        section_title=section.title,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # ReACT循环
    tool_calls_count = 0
    max_iterations = 5  # 最大迭代轮数
    min_tool_calls = 3  # 最少工具调用次数
    conflict_retries = 0  # 工具调用与Final Answer同时出现的连续冲突次数
    used_tools = set()  # 记录已调用过的工具名
    all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    # 报告上下文，用于InsightForge的子问题生成
    report_context = f"章节标题: {section.title}\n模拟需求: {agent.simulation_requirement}"

    for iteration in range(max_iterations):
        if progress_callback:
            progress_callback(
                "generating",
                int((iteration / max_iterations) * 100),
                t(
                    "progress.deepSearchAndWrite",
                    current=tool_calls_count,
                    max=agent.MAX_TOOL_CALLS_PER_SECTION,
                ),
            )

        # 调用LLM
        response = agent.llm.chat(
            messages=messages, temperature=0.5, max_tokens=settings.report_agent_max_tokens
        )

        # 检查 LLM 返回是否为 None（API 异常或内容为空）
        if response is None:
            logger.warning(
                t("report.sectionIterNone", title=section.title, iteration=iteration + 1)
            )
            # 如果还有迭代次数，添加消息并重试
            if iteration < max_iterations - 1:
                messages.append({"role": "assistant", "content": "（响应为空）"})
                messages.append({"role": "user", "content": "请继续生成内容。"})
                continue
            # 最后一次迭代也返回 None，跳出循环进入强制收尾
            break

        logger.debug(f"LLM响应: {response[:200]}...")

        # 解析一次，复用结果
        tool_calls = agent._parse_tool_calls(response)
        has_tool_calls = bool(tool_calls)
        has_final_answer = "Final Answer:" in response

        # ── 冲突处理：LLM 同时输出了工具调用和 Final Answer ──
        if has_tool_calls and has_final_answer:
            conflict_retries += 1
            logger.warning(
                t(
                    "report.sectionConflict",
                    title=section.title,
                    iteration=iteration + 1,
                    conflictCount=conflict_retries,
                )
            )

            if conflict_retries <= 2:
                # 前两次：丢弃本次响应，要求 LLM 重新回复
                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "【格式错误】你在一次回复中同时包含了工具调用和 Final Answer，这是不允许的。\n"
                            "每次回复只能做以下两件事之一：\n"
                            "- 调用一个工具（输出一个 <tool_call> 块，不要写 Final Answer）\n"
                            "- 输出最终内容（以 'Final Answer:' 开头，不要包含 <tool_call>）\n"
                            "请重新回复，只做其中一件事。"
                        ),
                    }
                )
                continue
            else:
                # 第三次：降级处理，截断到第一个工具调用，强制执行
                logger.warning(
                    t(
                        "report.sectionConflictDowngrade",
                        title=section.title,
                        conflictCount=conflict_retries,
                    )
                )
                first_tool_end = response.find("</tool_call>")
                if first_tool_end != -1:
                    response = response[: first_tool_end + len("</tool_call>")]
                    tool_calls = agent._parse_tool_calls(response)
                    has_tool_calls = bool(tool_calls)
                has_final_answer = False
                conflict_retries = 0

        # 记录 LLM 响应日志
        if agent.report_logger:
            agent.report_logger.log_llm_response(
                section_title=section.title,
                section_index=section_index,
                response=response,
                iteration=iteration + 1,
                has_tool_calls=has_tool_calls,
                has_final_answer=has_final_answer,
            )

        # ── 情况1：LLM 输出了 Final Answer ──
        if has_final_answer:
            # 工具调用次数不足，拒绝并要求继续调工具
            if tool_calls_count < min_tool_calls:
                messages.append({"role": "assistant", "content": response})
                unused_tools = all_tools - used_tools
                unused_hint = (
                    f"（这些工具还未使用，推荐用一下他们: {', '.join(unused_tools)}）"
                    if unused_tools
                    else ""
                )
                messages.append(
                    {
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    }
                )
                continue

            # 正常结束
            final_answer = response.split("Final Answer:")[-1].strip()
            logger.info(t("report.sectionGenDone", title=section.title, count=tool_calls_count))

            if agent.report_logger:
                agent.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count,
                )
            return final_answer

        # ── 情况2：LLM 尝试调用工具 ──
        if has_tool_calls:
            # 工具额度已耗尽 → 明确告知，要求输出 Final Answer
            if tool_calls_count >= agent.MAX_TOOL_CALLS_PER_SECTION:
                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=agent.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    }
                )
                continue

            # 只执行第一个工具调用
            call = tool_calls[0]
            if len(tool_calls) > 1:
                logger.info(
                    t("report.multiToolOnlyFirst", total=len(tool_calls), toolName=call["name"])
                )

            if agent.report_logger:
                agent.report_logger.log_tool_call(
                    section_title=section.title,
                    section_index=section_index,
                    tool_name=call["name"],
                    parameters=call.get("parameters", {}),
                    iteration=iteration + 1,
                )

            result = agent._execute_tool(
                call["name"], call.get("parameters", {}), report_context=report_context
            )

            if agent.report_logger:
                agent.report_logger.log_tool_result(
                    section_title=section.title,
                    section_index=section_index,
                    tool_name=call["name"],
                    result=result,
                    iteration=iteration + 1,
                )

            tool_calls_count += 1
            used_tools.add(call["name"])

            # 构建未使用工具提示
            unused_tools = all_tools - used_tools
            unused_hint = ""
            if unused_tools and tool_calls_count < agent.MAX_TOOL_CALLS_PER_SECTION:
                unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list="、".join(unused_tools))

            messages.append({"role": "assistant", "content": response})
            messages.append(
                {
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=agent.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                }
            )
            continue

        # ── 情况3：既没有工具调用，也没有 Final Answer ──
        messages.append({"role": "assistant", "content": response})

        if tool_calls_count < min_tool_calls:
            # 工具调用次数不足，推荐未用过的工具
            unused_tools = all_tools - used_tools
            unused_hint = (
                f"（这些工具还未使用，推荐用一下他们: {', '.join(unused_tools)}）"
                if unused_tools
                else ""
            )

            messages.append(
                {
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                }
            )
            continue

        # 工具调用已足够，LLM 输出了内容但没带 "Final Answer:" 前缀
        # 直接将这段内容作为最终答案，不再空转
        logger.info(t("report.sectionNoPrefix", title=section.title, count=tool_calls_count))
        final_answer = response.strip()

        if agent.report_logger:
            agent.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count,
            )
        return final_answer

    # 达到最大迭代次数，强制生成内容
    logger.warning(t("report.sectionMaxIter", title=section.title))
    messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})

    response = agent.llm.chat(
        messages=messages, temperature=0.5, max_tokens=settings.report_agent_max_tokens
    )

    # 检查强制收尾时 LLM 返回是否为 None
    if response is None:
        logger.error(t("report.sectionForceFailed", title=section.title))
        final_answer = t("report.sectionGenFailedContent")
    elif "Final Answer:" in response:
        final_answer = response.split("Final Answer:")[-1].strip()
    else:
        final_answer = response

    # 记录章节内容生成完成日志
    if agent.report_logger:
        agent.report_logger.log_section_content(
            section_title=section.title,
            section_index=section_index,
            content=final_answer,
            tool_calls_count=tool_calls_count,
        )

    return final_answer
