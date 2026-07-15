import asyncio
import os
import sys

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.app.config import settings
from src.app.database import init_db
from src.app.models.entities import User, Saree
from src.app.security import get_password_hash

async def seed():
    print("Initializing database tables...")
    await init_db()
    
    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(bind=engine, class_=AsyncSession)
    
    async with Session() as db:
        # Check if admin already exists
        from sqlalchemy import select
        res = await db.execute(select(User).where(User.email == "owner@zari.com"))
        if res.scalar_one_or_none():
            print("Database already seeded.")
            return
            
        print("Creating admin account owner@zari.com...")
        admin = User(
            email="owner@zari.com",
            password_hash=get_password_hash("securepassword123"),
            first_name="Meera",
            last_name="Sen",
            role="admin"
        )
        db.add(admin)
        
        print("Creating mock sarees catalog...")
        saree1 = Saree(
            title="Royal Crimson Banarasi Silk Saree",
            description="Exquisite handwoven Banarasi pure silk saree featuring detailed gold zari embroidery and elegant borders. Perfect for bridal and festive occasions.",
            price=4999.00,
            fabric="Banarasi Silk",
            color="Crimson Red",
            image_url="/static/images/saree_banarasi_red.png",
            secondary_images='[]',
            status="in_stock",
            clicks=24
        )
        
        saree2 = Saree(
            title="Midnight Blue Kanjeevaram Saree",
            description="Classic Midnight Blue Kanjeevaram pure silk saree with heavy gold weave details and contrast pallu, representing traditional Tamil heritage.",
            price=6500.00,
            fabric="Kanjeevaram Silk",
            color="Midnight Blue",
            image_url="/static/images/saree_kanjeevaram_blue.png",
            secondary_images='[]',
            status="in_stock",
            clicks=15
        )
        
        saree3 = Saree(
            title="Mint Green Organza Floral Saree",
            description="Ethereal mint green organza saree with delicate hand-painted floral motifs and rose gold border embellishments. Lightweight and extremely modern.",
            price=2200.00,
            fabric="Organza",
            color="Mint Green",
            image_url="/static/images/saree_organza_mint.png",
            secondary_images='[]',
            status="in_stock",
            clicks=8
        )
        
        saree4 = Saree(
            title="Sunset Orange Chanderi Cotton Saree",
            description="Breathable and elegant Sunset Orange Chanderi cotton saree with silver border highlights. Perfect for professional wear and daytime gatherings.",
            price=1800.00,
            fabric="Chanderi Cotton",
            color="Sunset Orange",
            image_url="/static/images/saree_organza_mint.png",
            secondary_images='[]',
            status="low_stock",
            clicks=11
        )
        
        saree5 = Saree(
            title="Golden Ivory Georgette Saree",
            description="Stunning Golden Ivory georgette saree featuring delicate sequin borders and a matching gold designer blouse piece. Drapes beautifully.",
            price=3500.00,
            fabric="Georgette",
            color="Golden Ivory",
            image_url="/static/images/saree_banarasi_red.png",
            secondary_images='[]',
            status="sold_out",
            clicks=5
        )
        
        db.add_all([saree1, saree2, saree3, saree4, saree5])
        await db.commit()
        print("Saree database successfully seeded with Admin (owner@zari.com / securepassword123) and 5 sarees.")

if __name__ == "__main__":
    asyncio.run(seed())
