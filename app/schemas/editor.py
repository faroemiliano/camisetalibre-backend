"""Documento completo del editor v2, incluidos recursos y personalizaciones ocultas."""
import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Coordinate = Annotated[float, Field(ge=-10000, le=10000, allow_inf_nan=False)]
Dimension = Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)]
ImageData = Annotated[str, StringConstraints(max_length=3000000, pattern=r"^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/]+={0,2}$")]
Side = Literal["front", "back"]
Garment = Literal["shirt", "short"]
Model = Literal["crew-neck", "v-neck", "polo", "sleeveless"]
PATTERNS = {"plain", "stripes", "diagonal", "hoops", "halves", "checks", "chevron", "cut-stripes-05"} | {f"catalog-{i:02}" for i in range(1, 29) if i != 5}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Colors(StrictModel):
    base: Color
    sleeves: Color
    collar: Color
    detail: Color
    accent: Color | None = None

    @field_validator("accent")
    @classmethod
    def non_null_accent(cls, value):
        if value is None:
            raise ValueError("Omití el color opcional en lugar de enviar null.")
        return value


class PositionedObject(StrictModel):
    id: str = Field(min_length=1, max_length=200)
    x: Coordinate
    y: Coordinate
    rotation: Coordinate


class Rectangle(PositionedObject):
    type: Literal["rect"]
    width: Dimension
    height: Dimension
    fill: Color


class Line(PositionedObject):
    type: Literal["line"]
    length: Dimension
    stroke: Color
    strokeWidth: Dimension


class TextObject(PositionedObject):
    type: Literal["text"]
    role: Literal["name", "number"]
    text: str = Field(max_length=80)
    width: Dimension
    fontSize: Dimension
    fontFamily: Literal["Arial", "Georgia", "Impact", "Verdana", "Courier New"]
    fill: Color
    outline: Color
    outlineWidth: float = Field(ge=0, le=20, allow_inf_nan=False)


class ImageObject(PositionedObject):
    type: Literal["image"]
    role: Literal["logo", "sponsor"]
    width: Dimension
    height: Dimension
    original: ImageData
    removeBackground: bool
    tolerance: float = Field(ge=0, le=441, allow_inf_nan=False)
    interior: bool
    tint: Color | None
    outline: Color
    outlineWidth: float = Field(ge=0, le=20, allow_inf_nan=False)


EditorObject = Annotated[Rectangle | Line | TextObject | ImageObject, Field(discriminator="type")]
ObjectList = Annotated[list[EditorObject], Field(max_length=80)]


class GarmentObjects(StrictModel):
    front: ObjectList
    back: ObjectList


class DocumentColors(StrictModel):
    shirt: Colors
    short: Colors


class DocumentObjects(StrictModel):
    shirt: GarmentObjects
    short: GarmentObjects

    @model_validator(mode="after")
    def unique_objects(self):
        objects = self.shirt.front + self.shirt.back + self.short.front + self.short.back
        if len({item.id for item in objects}) != len(objects):
            raise ValueError("Los elementos deben tener identificadores únicos.")
        if sum(isinstance(item, ImageObject) and item.role == "sponsor" for item in objects) > 6:
            raise ValueError("El máximo es de seis sponsors por diseño.")
        return self


class Customization(StrictModel):
    model: Model
    colors: DocumentColors
    objects: DocumentObjects


class PatternSettings(StrictModel):
    width: float = Field(ge=20, le=160, allow_inf_nan=False)
    gap: float = Field(ge=20, le=200, allow_inf_nan=False)
    angle: float = Field(ge=-60, le=60, allow_inf_nan=False)
    offset: float = Field(ge=-150, le=150, allow_inf_nan=False)
    position: float = Field(ge=140, le=550, allow_inf_nan=False)
    accentWidth: float = Field(ge=0, le=24, allow_inf_nan=False)


class KitDocument(Customization):
    version: Literal[2]
    pattern: str = Field(max_length=64)
    designSource: Literal["catalog", "custom"] | None = None
    customDesign: dict[Side, ImageData] | None = None
    designStates: dict[str, Customization] | None = None
    catalogPalettes: dict[str, Colors] | None = None
    patternSettings: dict[Literal["stripes", "diagonal", "chevron"], PatternSettings] | None = None

    @field_validator("designSource", "customDesign", "designStates", "catalogPalettes", "patternSettings")
    @classmethod
    def non_null_optional(cls, value):
        if value is None:
            raise ValueError("Omití los campos opcionales en lugar de enviar null.")
        return value

    @field_validator("pattern")
    @classmethod
    def valid_pattern(cls, value):
        if value not in PATTERNS:
            raise ValueError("Patrón no disponible.")
        return value

    @field_validator("designStates", "catalogPalettes")
    @classmethod
    def valid_keys(cls, value, info):
        if value is None:
            return value
        allowed = PATTERNS | {"custom"} if info.field_name == "designStates" else {key for key in PATTERNS if re.fullmatch(r"catalog-\d{2}|cut-stripes-05", key)}
        if not set(value).issubset(allowed):
            raise ValueError("Diseño de catálogo no disponible.")
        return value

    @model_validator(mode="after")
    def document_size(self):
        if len(json.dumps(self.model_dump(exclude_unset=True), ensure_ascii=False).encode()) > 32 * 1024 * 1024:
            raise ValueError("El conjunto supera el límite de 32 MB.")
        return self


class EditorUI(StrictModel):
    product: Garment
    side: Side
    activeTool: Literal["design", "colors", "artwork", "layers", "properties"]


class WorkspaceInput(StrictModel):
    document: KitDocument
    ui: EditorUI
    expectedRevision: int = Field(ge=0, le=2147483646, strict=True)


class BudgetPreference(StrictModel):
    productId: str = Field(min_length=1, max_length=32)
    fabricId: str = Field(min_length=1, max_length=32)
    quantity: int = Field(ge=1, le=10000, strict=True)


class PreferencesInput(StrictModel):
    budget: BudgetPreference
    expectedRevision: int = Field(ge=0, le=2147483646, strict=True)
