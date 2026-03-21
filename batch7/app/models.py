from pydantic import BaseModel


class Mensagem(BaseModel):
    texto: str