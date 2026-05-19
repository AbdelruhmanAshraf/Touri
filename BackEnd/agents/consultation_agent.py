"""
Consultation Agent — recommends the best country based on user constraints.
"""

import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.llm import get_chat_llm
from data.countries import SUPPORTED_COUNTRIES
from schemas.responses import AgentStep

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Touri Consultation Agent — an expert travel advisor for the Middle East and North Africa.

Your role is to compare our supported countries (Egypt, Saudi Arabia, Qatar, Turkey, Morocco) and recommend the best fit for the user based on their budget, number of travelers, and tourism type (standard vs. medical).

Supported Countries:
{countries_info}

User Persona Context: {persona_context}
Language: {language}

If the user asks for Medical Tourism, highlight countries like Turkey (hair transplants, cosmetic), Egypt (dental, affordable), Saudi Arabia (advanced hospitals), Morocco (wellness retreats), or Qatar (sports medicine, luxury wellness).

Provide a ranked recommendation (e.g., #1 Country, #2 Country) with a clear justification. If the budget is too low for a certain country, mention that.
Format with emojis. If the user prefers Arabic, respond in Arabic.
"""

def run_consultation(
    user_message: str,
    num_travelers: int = 1,
    total_budget_usd: float = 0.0,
    tourism_type: str = "standard",
    persona_context: str = "",
    language: str = "en",
) -> tuple[str, dict, list[AgentStep]]:
    
    trace: list[AgentStep] = []
    
    trace.append(AgentStep(
        agent="Consultation Agent",
        action="Analyzing cross-country options",
        reasoning=f"Comparing 5 countries for {num_travelers} travelers with ${total_budget_usd} budget ({tourism_type} tourism)",
    ))
    
    countries_info = ""
    for c_id, c_data in SUPPORTED_COUNTRIES.items():
        countries_info += f"- {c_data['name']} {c_data['flag']}: Currency: {c_data['currency']}, Medical Specialties: {', '.join(c_data['medical_specialties'])}\n"
    
    try:
        llm = get_chat_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", """User request: {user_message}

Parameters:
Travelers: {num_travelers}
Total Budget: ${total_budget_usd}
Tourism Type: {tourism_type}

Please provide your ranked recommendation and advice.
Persona: {persona_context}"""),
        ])
        chain = prompt | llm | StrOutputParser()
        response = str(chain.invoke({
            "user_message": user_message,
            "countries_info": countries_info,
            "num_travelers": num_travelers,
            "total_budget_usd": total_budget_usd,
            "tourism_type": tourism_type,
            "persona_context": persona_context or "No preferences set.",
            "language": language,
        }))
        trace[-1].result = "Recommendation generated successfully"
    except Exception as e:
        logger.warning(f"LLM error in Consultation Agent: {e}")
        response = f"Based on your criteria, we recommend checking out Turkey or Egypt for medical tourism, and Saudi Arabia or Qatar for luxury stays."
        trace[-1].result = f"Used fallback (LLM error: {e})"

    consultation_dict = {
        "travelers": num_travelers,
        "budget_usd": total_budget_usd,
        "tourism_type": tourism_type,
        "countries_considered": list(SUPPORTED_COUNTRIES.keys())
    }

    return response, consultation_dict, trace
