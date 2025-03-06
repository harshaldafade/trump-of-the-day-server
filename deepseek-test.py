
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
print(os.getenv("DSK_API_KEY"))

client = OpenAI(api_key=os.getenv("DSK_API_KEY"), base_url="https://api.deepseek.com")

content = """
President Trump has signed an executive order designating English as the official language of the U.S., the first such designation in the country's history.

The order, which Trump signed on Saturday, rescinds a policy issued by former President Bill Clinton requiring agencies to provide assistance programs for people with limited English proficiency, according to a White House fact sheet. The order allows agencies to voluntarily keep those support systems in place.

"A nationally designated language is at the core of a unified and cohesive society, and the United States is strengthened by a citizenry that can freely exchange ideas in one shared language," the order said.

English is already the official language in more than 30 states, but Trump's executive order comes at a time when the number of people in the United States who speak languages other than English continues to grow. Roughly one in 10 people now speak a language other than English, more than triple the amount compared to 1980, according to 2022 data from the U.S. Census.

Trump's order echoes a longtime campaign pledge and is a move the White House said will "promotes unity, cultivate a shared American culture for all citizens, ensure consistency in government operations, and create a pathway to civic engagement."

At the same time, some advocacy organizations say the order will hurt immigrant communities and those looking for assistance learning English.

Roman Palomares, who heads the League of United Latin American Citizens, criticized the Trump administration's move in a statement issued ahead of the order's official signing.

"Our Founding Fathers enshrined freedom of speech in the First Amendment without limiting it to one language. They envisioned a nation where diversity of thought, culture, and expression would be its greatest strength," said Palomares.

"Declaring English as the only official language directly contradicts that vision," he added. "America thrives when we embrace inclusivity, not when we silence the voices of millions who contribute to its success.

summarize the above news in 100 words.
"""

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": content},
    ],
    stream=False
)

print(response.choices[0].message.content)