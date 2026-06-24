from datetime import datetime
from app.mongodb_service import farm_images, farm_image_history

HISTORY_KEEP_DATA = 30  # how many most-recent uploads per farm keep full image bytes


def save_farm_image(farm_id: str, farm_name: str, image_data: str, content_type: str) -> dict:
    """
    Save a base64 image for a farm as the CURRENT image (replaces any
    existing current image — one current image per farm at a time),
    and also append it to that farm's permanent upload history.
    """
    now = datetime.utcnow()

    farm_images.delete_many({"farmId": farm_id})
    doc = {
        "farmId": farm_id,
        "farmName": farm_name,
        "contentType": content_type,
        "data": image_data,
        "uploadedAt": now
    }
    result = farm_images.insert_one(doc)

    farm_image_history.insert_one({
        "farmId": farm_id,
        "farmName": farm_name,
        "contentType": content_type,
        "data": image_data,
        "uploadedAt": now,
        "size": len(image_data)
    })
    _prune_history_data(farm_id)

    return {"status": "success", "id": str(result.inserted_id)}


def _prune_history_data(farm_id: str):
    """
    Keep full image bytes only for the most recent HISTORY_KEEP_DATA
    uploads of this farm. Older history rows keep their metadata but
    have `data` stripped.
    """
    cursor = (
        farm_image_history
        .find({"farmId": farm_id}, {"_id": 1})
        .sort("uploadedAt", -1)
        .skip(HISTORY_KEEP_DATA)
    )
    old_ids = [doc["_id"] for doc in cursor]
    if old_ids:
        farm_image_history.update_many(
            {"_id": {"$in": old_ids}},
            {"$unset": {"data": ""}}
        )


def get_farm_image(farm_id: str) -> dict | None:
    """Current image for a farm (raw bytes route)."""
    doc = farm_images.find_one({"farmId": farm_id}, {"_id": 0})
    return doc


def get_farm_image_meta(farm_id: str) -> dict:
    """
    Lightweight check used on page load: does this farm have a saved
    image, and when was it uploaded — without fetching the image bytes.
    """
    doc = farm_images.find_one({"farmId": farm_id}, {"_id": 0, "data": 0})
    if not doc:
        return {"hasImage": False, "ts": None, "farmName": None}
    return {"hasImage": True, "ts": doc["uploadedAt"].isoformat(), "farmName": doc.get("farmName")}

def get_farm_image_history(farm_id: str) -> list[dict]:
    """Every upload ever made for this farm, newest first."""
    cursor = (
        farm_image_history
        .find({"farmId": farm_id}, {"_id": 0})
        .sort("uploadedAt", -1)
    )
    out = []
    for doc in cursor:
        doc["uploadedAt"] = doc["uploadedAt"].isoformat()
        out.append(doc)
    return out


def delete_current_farm_image(farm_id: str):
    """
    Removes only the CURRENT image pointer for a farm. The permanent
    upload history is left untouched on purpose.
    """
    farm_images.delete_many({"farmId": farm_id})