import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_chatgpt_response(prompt: str, system_role: str = "You are a helpful assistant."):
    try:
        response = client.chat.completions.create(
            model=getattr(settings, "OPENAI_MODEL", "gpt-3.5-turbo"),
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()

        # Remove fenced code blocks if present.
        if content.startswith("```"):
            content = re.sub(r"```json|```", "", content).strip()

        # Extract first JSON object if the model included extra text.
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content_json = content[start : end + 1].strip()
        else:
            content_json = content

        parsed = json.loads(content_json)
        return parsed

    except json.JSONDecodeError as json_err:
        return {"error": "JSON parsing error", "raw_content": content, "details": str(json_err)}
    except Exception as e:
        return {"error": str(e)}
