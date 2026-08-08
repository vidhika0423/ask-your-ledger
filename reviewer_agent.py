import os
import re
from dotenv import load_dotenv
from groq import Groq

from finance_agent import fuse_context, retrieve_graph_facts, retrieve_raptor_context
load_dotenv()

groq_client = Groq(api_key = os.environ["GROQ_API_KEY"])
GROQ_MODEL =  "llama-3.3-70b-versatile"

def extract_numbers(text):
    """Pulls out dollar amounts and invoice IDs"""
    dollar_amounts = re.findall(r"\$[\d,]+(?:\.\d+)?",text)
    invoice_ids = re.findall(r"INV-\d+",text)
    return set(dollar_amounts), set(invoice_ids)

def numeric_grounding_check(answer, context):
    """every number/invoice ID claimed in the answer must appear in the context"""
    answer_amounts, answer_invoices = extract_numbers(answer)
    context_amounts, context_invoices = extract_numbers(context)

    # must be false
    ungrounded_amounts = answer_amounts - context_amounts
    ungrounded_invoices = answer_invoices - context_invoices
    # !(ungrounded_amounts && ungrounded_invoices)
    passed = not ungrounded_amounts and not ungrounded_invoices

    return {
        "passed": passed,
        "ungrounded_amounts": ungrounded_amounts,
        "ungrounded_invoices": ungrounded_invoices,
    }

def llm_grounding_check(question, context, answer):
    """Ask the LLM to check evry claim in the answer against the context"""
    prompt = f"""
    You are a strict fact-checker. Below is a QUESTION, the CONTEXT 
    that was available to answer it, and a DRAFT ANSWER that was produced
    Check whether every factual claim in the DRAFT ANSWER in actually supported
    by the CONTEXT.
    Do not check spelling or style - only check if claims are grounded in thet 
    given facts.

    Respond in exactly this format:
    VERDICT: GROUNDED or NOT_GROUNDED
    CONFIDENCE: a number between 0.0 and 1.0
    ISSUES: list any unsupported claims, or write "none"
    CONTEXT:
    {context}
    QUESTION: {question}
    DRAFT ANSWER: {answer}
    """

    response = groq_client.chat.completions.create(
        model = GROQ_MODEL,
        max_tokens = 200,
        messages = [{"role":"user", "content":prompt}],
    )
    return response.choices[0].message.content.strip()

def review_answer(question, answer, graph_facts, raptor_results):
    context = fuse_context(graph_facts, raptor_results)

    print("numeric groundinf check (rule based, cheap)")
    numeric_result = numeric_grounding_check(answer, context)
    print(numeric_result)       

    print("\nLLM grounding check\n")
    llm_result = llm_grounding_check(question, context, answer)
    print(llm_result)

    overall_passed = numeric_result["passed"] and "NOT_GROUNDED" not in llm_result
    print(f"\n ---OVERALL: {'APPROVED' if overall_passed else 'REJECTED - would loop back to retrival'} ---")

    return overall_passed


if __name__ == "__main__":
    from groq import Groq as _Groq

    question = "Are any subsidiaries of Acme Holdings overdue, and what's the late payment penalty?"
    graph_facts = retrieve_graph_facts()
    raptor_results = retrieve_raptor_context(question)
    context = fuse_context(graph_facts, raptor_results)

    draft_prompt = f"""
    You are a finance assistant. Answer the question using ONLY the facts below.
    {context}
    Question:{question}
    Answer concisely, citing which invoice IDs or contract sections your answer relies on.
    """
    draft_response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": draft_prompt}],
    )
    draft_answer = draft_response.choices[0].message.content.strip()

    print(f"Draft answer:\n{draft_answer}\n")
    review_answer(question, draft_answer, graph_facts, raptor_results)
