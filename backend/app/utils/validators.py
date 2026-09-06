from beanie import PydanticObjectId


def is_valid_object_id(value: str) -> bool:
    try:
        PydanticObjectId(value)
        return True
    except Exception:
        return False
