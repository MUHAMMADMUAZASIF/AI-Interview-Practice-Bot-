import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="AI Interview Coach", page_icon="🎤", layout="wide")


# ---------- API helpers ----------
def api(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{BACKEND}{path}", timeout=120, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get("detail", e.response.text)
        except Exception:
            detail = str(e)
        st.error(f"Backend error: {detail}")
    except requests.RequestException as e:
        st.error(f"Cannot reach backend at {BACKEND}: {e}")
    return None


def reset():
    for k in ("session_id", "history", "current_q", "q_num", "total", "finished", "summary"):
        st.session_state.pop(k, None)


def build_report() -> str:
    s, hist = st.session_state.summary, st.session_state.history
    lines = ["# Interview Report\n",
             f"**Average score:** {s['average_score']}/10 | **Readiness:** {s['readiness']}\n",
             f"> {s['headline']}\n", "## Strengths", *[f"- {x}" for x in s["top_strengths"]],
             "\n## Areas to improve", *[f"- {x}" for x in s["areas_to_improve"]],
             "\n## Study plan", *[f"- {x}" for x in s["study_plan"]], "\n## Question breakdown"]
    for i, h in enumerate(hist, 1):
        ev = h["evaluation"]
        lines += [f"\n### Q{i}: {h['question']}", f"**Your answer:** {h['answer']}", f"**Score:** {ev['score']}/10",
                  "**Strengths:** " + "; ".join(ev["strengths"]), "**Improve:** " + "; ".join(ev["improvements"]),
                  f"**Ideal answer:** {ev['ideal_answer']}"]
    return "\n".join(lines)


# ---------- Sidebar: setup ----------
with st.sidebar:
    st.title("🎤 Interview Coach")
    active = "session_id" in st.session_state
    role = st.text_input("Target role", "Backend Engineer", disabled=active)
    itype = st.selectbox("Interview type", ["technical", "hr", "mixed"], disabled=active)
    level = st.selectbox("Level", ["junior", "mid", "senior"], index=1, disabled=active)
    n = st.slider("Number of questions", 3, 10, 5, disabled=active)
    focus = st.text_input("Focus areas (optional)", placeholder="Python, SQL, system design", disabled=active)

    if not active:
        if st.button("Start interview", type="primary", use_container_width=True):
            with st.spinner("Preparing your first question..."):
                data = api("POST", "/sessions", json={
                    "role": role, "interview_type": itype, "difficulty": level,
                    "num_questions": n, "focus_areas": focus or None})
            if data:
                st.session_state.update(session_id=data["session_id"], current_q=data["question"],
                                        q_num=1, total=data["total_questions"], history=[], finished=False)
                st.rerun()
    else:
        st.progress(min(len(st.session_state.history) / st.session_state.total, 1.0),
                    text=f"{len(st.session_state.history)}/{st.session_state.total} answered")
        if st.button("Abandon / new interview", use_container_width=True):
            reset()
            st.rerun()

# ---------- Main ----------
if "session_id" not in st.session_state:
    st.header("Practice interviews with instant, honest feedback")
    st.write("Pick a role and interview type in the sidebar, then answer questions one by one. "
             "You'll get a score and coaching after every answer, plus a full report at the end.")
    st.stop()

# Past turns
for i, h in enumerate(st.session_state.history, 1):
    with st.chat_message("assistant"):
        st.markdown(f"**Q{i}.** {h['question']}")
    with st.chat_message("user"):
        st.write(h["answer"])
    ev = h["evaluation"]
    with st.chat_message("assistant", avatar="📝"):
        st.markdown(f"**Score: {ev['score']}/10**")
        cols = st.columns(len(ev["criteria"]) or 1)
        for col, (k, v) in zip(cols, ev["criteria"].items()):
            col.metric(k.capitalize(), f"{v}/10")
        c1, c2 = st.columns(2)
        c1.markdown("**Strengths**\n" + "\n".join(f"- {x}" for x in ev["strengths"]))
        c2.markdown("**To improve**\n" + "\n".join(f"- {x}" for x in ev["improvements"]))
        with st.expander("See a strong answer outline"):
            st.write(ev["ideal_answer"])

# Current question or final report
if not st.session_state.finished:
    with st.chat_message("assistant"):
        st.markdown(f"**Q{st.session_state.q_num}.** {st.session_state.current_q}")
    answer = st.chat_input("Type your answer...")
    if answer:
        with st.spinner("Evaluating your answer..."):
            res = api("POST", f"/sessions/{st.session_state.session_id}/answer", json={"answer": answer})
        if res:
            st.session_state.history.append({"question": st.session_state.current_q, "answer": answer,
                                             "evaluation": res["evaluation"]})
            st.session_state.finished = res["finished"]
            if res["next_question"]:
                st.session_state.current_q = res["next_question"]
                st.session_state.q_num = res["question_number"]
            st.rerun()
else:
    st.divider()
    st.header("📊 Performance summary")
    if "summary" not in st.session_state:
        with st.spinner("Writing your report..."):
            st.session_state.summary = api("POST", f"/sessions/{st.session_state.session_id}/summary")
    s = st.session_state.summary
    if s:
        a, b = st.columns(2)
        a.metric("Average score", f"{s['average_score']}/10")
        b.metric("Readiness", s["readiness"])
        st.info(s["headline"])
        st.bar_chart({f"Q{i}": h["evaluation"]["score"] for i, h in enumerate(st.session_state.history, 1)})
        c1, c2 = st.columns(2)
        c1.subheader("Strengths")
        c1.markdown("\n".join(f"- {x}" for x in s["top_strengths"]))
        c2.subheader("Areas to improve")
        c2.markdown("\n".join(f"- {x}" for x in s["areas_to_improve"]))
        st.subheader("Study plan")
        st.markdown("\n".join(f"{i}. {x}" for i, x in enumerate(s["study_plan"], 1)))
        st.success(s["closing_message"])
        st.download_button("Download report (.md)", build_report(), "interview_report.md", "text/markdown")
        if st.button("Start another interview"):
            reset()
            st.rerun()
