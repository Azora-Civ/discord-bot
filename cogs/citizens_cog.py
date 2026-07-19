from discord import Member

from models.ShownException import NotFoundException
from repositories.citizens import CitizenRepository


async def ign_from_user(user: Member) -> str:
    p_repo = CitizenRepository()
    person = await p_repo.fetch_by_user_id(user.id)
    if not person:
        raise NotFoundException("User is not registered as a citizen/resident.")

    return person.in_game_name
