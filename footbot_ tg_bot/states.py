from aiogram.fsm.state import State, StatesGroup

class PlayerEdit(StatesGroup):
    waiting_for_stat_name = State()
    waiting_for_value = State()


class InitialSetup(StatesGroup):
    waiting_for_player_count = State()
    waiting_for_timezone = State()
    waiting_for_match_day = State()
    waiting_for_match_times = State()
    waiting_for_skill_level = State()
    waiting_for_age_group = State()
    waiting_for_gender = State()
    waiting_for_venue = State()
    waiting_for_cost = State()
    waiting_for_championship = State()

class LegionnaireCreate(StatesGroup):
    waiting_for_name = State()
    waiting_for_attack = State()
    waiting_for_defense = State()
    waiting_for_speed = State()
    waiting_for_gk = State()

class MatchSettings(StatesGroup):
    waiting_for_player_count = State()
    waiting_for_skill_level = State()
    waiting_for_age_group = State()
    waiting_for_gender = State()
    waiting_for_cost = State()
    waiting_for_timezone = State()
    waiting_for_match_times = State()
    waiting_for_season_start = State()
    waiting_for_season_end = State()
    waiting_for_venue = State()
    waiting_for_location = State()
    waiting_for_payment_details = State()
    waiting_for_championship = State()

class PlayerSelfRegister(StatesGroup):
    waiting_for_name = State()
    waiting_for_attack = State()
    waiting_for_defense = State()
    waiting_for_speed = State()
    waiting_for_gk = State()

class CaptainSelection(StatesGroup):
    waiting_for_captains = State()
    waiting_for_pick = State()

class MatchResult(StatesGroup):
    waiting_for_score = State()
    waiting_for_exists_decision = State()

class PlayerRating(StatesGroup):
    rating_points = State()
    choosing_defender = State()
class MatchScoring(StatesGroup):
    waiting_for_scorers = State()
    waiting_for_assist = State()

class PlayerStatEdit(StatesGroup):
    waiting_for_name = State()
    waiting_for_attack = State()
    waiting_for_defense = State()
    waiting_for_speed = State()
    waiting_for_gk = State()
    waiting_for_value = State()

class PairsBuilder(StatesGroup):
    selecting_left = State()
    selecting_right = State()
    waiting_for_attack = State()
    waiting_for_defense = State()
    waiting_for_speed = State()
    waiting_for_gk = State()

class MatchEvents(StatesGroup):
    """States for entering match events (goals, cards) after score entry"""
    entering_goals = State()
    entering_goal_times = State()
    entering_autogoals = State()
    entering_autogoal_times = State()
    entering_cards = State()
    entering_card_times = State()
