import json
import re
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_chatgpt_response(prompt: str, system_role: str = "You are a helpful assistant."):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content.strip()

        # Remove triple backticks and extract JSON block if present
        if content.startswith("```json"):
            content = re.sub(r"```json|```", "", content).strip()
        
        # Attempt to parse as JSON
        return json.loads(content)

    except json.JSONDecodeError as json_err:
        return {"error": "JSON parsing error", "raw_content": content, "details": str(json_err)}
    except Exception as e:
        return {"error": str(e)}
