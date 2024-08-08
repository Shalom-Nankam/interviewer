from fastapi import FastAPI, HTTPException
from typing import Optional
import time, random, string, os, json
from pydantic import BaseModel
from api.llm import LLMManager
from resources.prompts import prompts
from utils.config import Config
from tests.testing_prompts import candidate_prompt
from resources.data import fixed_messages, topic_lists
from tests.candidate import complete_interview
from ui.coding import send_request

app = FastAPI()

class StartInterview(BaseModel):
    type: str
    difficulty: str
    topic: str
    requirements: str = ""

class Interaction(BaseModel):
    code: str
    message: str
    interview_path: str

@app.post("/start_interview/")
async def start_interview(item: StartInterview):
    try:
        config = Config()
        llm = LLMManager(config=config, prompts=prompts)
        for problem_statement_text in llm.get_problem(item.requirements, item.difficulty, item.topic, item.type):
            pass

        messages_interviewer = llm.init_bot(problem_statement_text, item.type)
        chat_display = [[None, fixed_messages["start"]]]

        messages_candidate = [
            {"role": "system", "content": candidate_prompt},
            {"role": "user", "content": f"Your problem: {problem_statement_text}"},
            {"role": "user", "content": chat_display[-1][1]},
        ]
        current_time = time.strftime("%Y%m%d-%H%M%S")
        random_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        interview_info =  {"difficulty": item.difficulty, "topic": item.topic, "type": item.type, "problem_statement": problem_statement_text, "chat_history": messages_candidate, "chat_display": chat_display, "messages_interviewer": messages_interviewer, "transcript": []}

        file_path = os.path.join("records", f"{current_time}-{random_suffix}.json")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as file:
            json.dump(interview_info, file, indent=4)

        return {"interview_path": file_path, "difficulty": item.difficulty, "topic": item.topic, "type": item.type, "problem_statement": problem_statement_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/interact")
async def interact_with_ai(chat: Interaction):
    try:
        if not os.path.exists(chat.interview_path):
            raise HTTPException(status_code=404, detail="Interview file not found")
        
        with open(chat.interview_path, 'r') as file:
            data = json.load(file) 
        chat_history = data["chat_history"]
        chat_display = data["chat_display"]
        chat_display.append([chat.message, None])

        config = Config()
        llm = LLMManager(config=config, prompts=prompts)
        # chat_history.append({"role": "assistant", "content": chat.message})
        for messages_interviewer, chat_display, previous_code, _ in send_request(
                chat.code, "", data["messages_interviewer"], chat_display, llm, tts=None, silent=True
            ):
                pass
        data["messages_interviewer"] = messages_interviewer
        data["chat_display"] = chat_display
        data["transcript"].append({"CANDIDATE_MESSAGE": chat.message})
        data["transcript"].append({"AI_INTERVIEWER": messages_interviewer[-1]["content"]})
        with open(chat.interview_path, "w") as file:
            json.dump(data, file, indent=4)
        return {
            "response": {
                "ai_interviewer": messages_interviewer[-1]
            }
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Interview file not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Error decoding interview file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/transcript")
async def get_transcript(interview_path: Optional[str]):
    try:
        if not os.path.exists(interview_path):
            raise HTTPException(status_code=404, detail="Interview file not found")
        
        with open(interview_path, 'r') as file:
            data = json.load(file) 

        return data["transcript"]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Interview file not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Error decoding interview file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
