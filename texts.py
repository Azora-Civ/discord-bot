from attr import dataclass


@dataclass
class CitizenApplicationModalTexts:
    citizenship_label: str = "Citizenship"
    username_label: str = "Minecraft Username"
    about_label: str = "What would you like to do in Azora?"
    duchy_label: str = "Which duchy or city do you want to join?"
    ack_label: str = "Acknowledgements"
    ack_law_label: str = "I will follow Azora's laws"
    ack_level_label: str = "I understand I start at level 1"


CITIZEN_APPLICATION_MODAL_TITLE = "Citizenship Application"
CITIZEN_APPLICATION_MODAL_SUBMITTED = "Registration request submitted!"

CITIZEN_APPLICATION_MODAL_SELF = CitizenApplicationModalTexts()
CITIZEN_APPLICATION_MODAL_OTHER = CitizenApplicationModalTexts(
    about_label="What would they like to do in Azora?",
    duchy_label="Which duchy or city do they want to join?",
    ack_law_label="They will follow Azora's laws",
    ack_level_label="They understand they start at level 1",
)
