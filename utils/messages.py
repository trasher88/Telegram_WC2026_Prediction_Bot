MAX_MESSAGE = 4000


async def safe_answer(msg, text):

    if len(text) <= MAX_MESSAGE:
        await msg.answer(text)
        return

    parts = []
    current = ""

    for line in text.splitlines(True):
        if len(current) + len(line) > MAX_MESSAGE:
            parts.append(current)
            current = line

        else:
            current += line

    if current:
        parts.append(current)

    for part in parts:
        await msg.answer(part)