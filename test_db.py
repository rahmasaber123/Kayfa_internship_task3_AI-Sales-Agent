import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient

# 1. تحميل المتغيرات فوراً
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("SetupCache")

def run_setup():
    # 2. التحقق من وجود الـ URI
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        logger.error("❌ CRITICAL ERROR: MONGO_URI not found in .env file!")
        return
    
    # تحديد قاعدة البيانات باسم 'user' كما طلبت
    db_name = "user" 
    
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        
        logger.info(f"🔗 Connected to database: {db_name}")
        
        # 3. التحقق من وجود الـ Collection
        collections = db.list_collection_names()
        
        if "semantic_cache" in collections:
            logger.info("ℹ️ Collection 'semantic_cache' already exists. Nothing to build.")
        else:
            logger.info("🚀 Building new collection: 'semantic_cache'...")
            db.create_collection("semantic_cache")
            
            # اختياري: إضافة فهرس (Index) افتراضي لتسريع البحث لاحقاً
            db["semantic_cache"].create_index("query")
            
            logger.info("✅ 'semantic_cache' created successfully.")
            
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")

if __name__ == "__main__":
    confirm = input("You are about to initialize 'semantic_cache' in DB 'user'. Proceed? (y/n): ")
    if confirm.lower() == 'y':
        run_setup()
    else:
        logger.warning("Operation aborted.")