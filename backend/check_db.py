import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal
import auth.models
import chat.models
import documents.models
import monitoring.models
from auth.models import User
from documents.models import Document

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "madhumahi210@gmail.com"))
        user = result.scalars().first()
        if not user:
            print("User not found.")
            return
        print(f"User: {user.email} (ID: {user.id})")
        
        docs_res = await session.execute(select(Document).where(Document.user_id == str(user.id)))
        docs = docs_res.scalars().all()
        print(f"Documents ({len(docs)}):")
        for d in docs:
            print(f"  - {d.filename} (ID: {d.id}, Status: {d.status})")

if __name__ == "__main__":
    asyncio.run(check())
