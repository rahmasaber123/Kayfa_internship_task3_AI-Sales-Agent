"""Data Access Layer for Courses, Roadmaps (MongoDB) and Pricing (JSON)."""
from __future__ import annotations
import json
from pathlib import Path
from src.memory.mongo import get_db

CATALOG_PATH = Path(__file__).resolve().parent.parent.parent / "catalog.json"

# ─────────────────────────────────────────────────────────────────────
# MONGODB QUERIES (COURSES & ROADMAPS)
# ─────────────────────────────────────────────────────────────────────

def search_courses(kb, track: str | None = None, level: str | None = None, limit: int = 5) -> list[dict]:
    db = get_db()
    query = {}
    
    if track:
        query["track"] = {"$regex": track, "$options": "i"}
    if level:
        query["level"] = {"$regex": level, "$options": "i"}
        
    results = list(db["courses"].find(query).limit(limit))
    
    for r in results:
        if "_id" in r: r["_id"] = str(r["_id"])
    return results

def get_course(kb, course_id: str) -> dict | None:
    db = get_db()
    course = db["courses"].find_one({"id": course_id})
    if course and "_id" in course: course["_id"] = str(course["_id"])
    return course

def get_roadmap(kb, roadmap_id: str) -> dict | None:
    db = get_db()
    roadmap = db["roadmaps"].find_one({"id": roadmap_id})
    if roadmap and "_id" in roadmap: roadmap["_id"] = str(roadmap["_id"])
    return roadmap

def list_diplomas(kb, limit: int = 10) -> list[dict]:
    db = get_db()
    results = list(db["roadmaps"].find({
        "$or": [
            {"type": "diploma"},
            {"id": {"$regex": "diploma", "$options": "i"}}
        ]
    }).limit(limit))
    
    for r in results:
        if "_id" in r: r["_id"] = str(r["_id"])
    return results

def list_tracks(kb, limit: int = 10) -> list[dict]:
    db = get_db()
    results = list(db["courses"].find({}).limit(limit))
    for r in results:
        if "_id" in r: r["_id"] = str(r["_id"])
    return results

# ─────────────────────────────────────────────────────────────────────
# PRICING LOOKUP (JSON)
# ─────────────────────────────────────────────────────────────────────

def get_pricing(kb, retriever, program_name: str | None = None) -> dict:
    if not CATALOG_PATH.exists():
        return {"error": f"Catalog file not found at {CATALOG_PATH}"}
    
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        all_items = data.get("programs", [])
        if not all_items:
            all_items = data.get("educational_tracks", []) + data.get("individual_courses", [])
            
        # 1. Handle general requests or missing arguments by returning EVERYTHING
        general_keywords = ["all", "الكل", "عام", "كورسات", "كورساتكم", "أسعار", "اسعار"]
        if not program_name or program_name.lower() in general_keywords:
            return {"catalog": all_items}
            
        # 2. Handle specific searches
        query = program_name.lower()
        match = next((item for item in all_items if query in item.get("name", "").lower()), None)
        
        if match:
            return {"name": match.get("name"), "price": match.get("price", "Contact Sales")}
            
        # 3. Fallback: If the specific course isn't found, don't crash! 
        # Just return the full catalog so the agent can figure it out.
        return {
            "note": f"Exact match for '{program_name}' not found. Here is the full catalog.", 
            "catalog": all_items
        }
        
    except Exception as e:
        return {"error": f"Error reading catalog: {e}"}