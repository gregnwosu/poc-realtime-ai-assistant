from typing import get_type_hints, Any, Dict, get_origin, get_args
from pydantic import BaseModel
import inspect
from typing import Optional, List, Dict as TypeDict, Union

def get_pydantic_schema(model_class: type[BaseModel]) -> Dict[str, Any]:
    """Extract schema from a Pydantic model including nested models"""
    schema = model_class.model_json_schema()
    properties = {}
    
    for prop_name, prop_info in schema.get("properties", {}).items():
        # Get the field type from the model
        field = model_class.model_fields[prop_name]
        field_type = field.annotation

        # Check if this field is another Pydantic model
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            # Recursively get the nested model's schema
            properties[prop_name] = get_pydantic_schema(field_type)
            # Add the field description if it exists
            
            if field.description:
                properties[prop_name]["description"] = field.description
        else:
            # Handle non-Pydantic fields as before
            cleaned_prop = {
                "type": prop_info.get("type", "string"),
                "description": prop_info.get("description", f"Field '{prop_name}'")
            }
            if "enum" in prop_info:
                cleaned_prop["enum"] = prop_info["enum"]
            properties[prop_name] = cleaned_prop
    
    return {
        "type": "object",
        "properties": properties,
        "required": schema.get("required", [])
    }

from typing import get_type_hints, Any, Dict, get_origin, get_args, Annotated
from pydantic import BaseModel
import inspect
from typing import Optional, List, Dict as TypeDict, Union

def is_annotated(tp):
    return get_origin(tp) is Annotated

def get_annotation_description(type_hint: Any) -> Optional[str]:
    """Extract description from annotated type if present"""
    if is_annotated(type_hint):
        args = get_args(type_hint)
        # Look through metadata for descriptions
        for arg in args[1:]:  # first arg is the actual type, the rest are metadata
            if isinstance(arg, dict) and "description" in arg:
                return arg["description"]
            elif isinstance(arg, str):
                return arg
    return None

def get_type_schema(type_hint: Any) -> Dict[str, Any]:
    """
    Recursively build schema for any type
    """
    # Check for description in Annotated type
    description = get_annotation_description(type_hint)
    
    # If it's an Annotated type, get the actual type
    if is_annotated(type_hint):
        type_hint = get_args(type_hint)[0]

    # Handle None/Optional
    if type_hint is type(None):
        schema = {"type": "null"}
        if description:
            schema["description"] = description
        return schema

    # Get origin and args for generic types
    origin = get_origin(type_hint)
    args = get_args(type_hint)

    # Handle Optional/Union types
    if origin is Union:
        types = [arg for arg in args if arg is not type(None)]
        if len(types) == 1:
            schema = get_type_schema(types[0])
            schema["nullable"] = True
            if description:
                schema["description"] = description
            return schema
        schema = {
            "anyOf": [get_type_schema(arg) for arg in types]
        }
        if description:
            schema["description"] = description
        return schema

    # Handle Lists
    if origin is list or origin is List:
        schema = {
            "type": "array",
            "items": get_type_schema(args[0])
        }
        if description:
            schema["description"] = description
        return schema

    # Handle Dictionaries
    if origin is dict or origin is TypeDict:
        schema = {
            "type": "object",
            "additionalProperties": get_type_schema(args[1])
        }
        if description:
            schema["description"] = description
        return schema

    # Handle Pydantic models
    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        schema = get_pydantic_schema(type_hint)
        if description:
            schema["description"] = description
        return schema

    # Handle basic types
    python_to_json_types = {
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array"
    }
    
    if type_hint in python_to_json_types:
        schema = {"type": python_to_json_types[type_hint]}
        if description:
            schema["description"] = description
        return schema

    # Default to string if type is unknown
    schema = {"type": "string"}
    if description:
        schema["description"] = description
    return schema

def build_function_descriptor(func) -> Dict[str, Any]:
    """
    Creates a JSON-like function descriptor by inspecting the function's
    signature, docstring, and type annotations.
    """
    doc = func.__doc__ or ""
    type_hints = get_type_hints(func,  include_extras=True)
    
    # Get return type schema if it exists
    return_type = type_hints.get('return')
    return_schema = get_type_schema(return_type) if return_type else None
    
    # Combine docstring with return type info
    full_description = doc.strip()
    if return_schema:
        return_desc = "\nReturns: " + str(return_schema)
        full_description = full_description + return_desc
    
    descriptor = {
        "type": "function",
        "name": func.__name__,
        "description": full_description,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }

    sig = inspect.signature(func)
    
    for param_name, param in sig.parameters.items():
        annotation = type_hints.get(param_name, str)
        descriptor["parameters"]["properties"][param_name] = get_type_schema(annotation)
        
        if param.default is inspect._empty:
            descriptor["parameters"]["required"].append(param_name)

    return descriptor