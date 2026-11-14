from typing import List
import pytest
from rorapp.actions.propose_replacing_proconsul import ProposeReplacingProconsulAction
from rorapp.classes.faction_status_item import FactionStatusItem
from rorapp.classes.random_resolver import FakeRandomResolver
from rorapp.models import AvailableAction, Campaign, Fleet, Game, Legion, Senator, War
from rorapp.effects.meta.effect_executor import execute_effects_and_manage_actions


def _setup_pass_recall_proposal(game: Game, proconsul: Senator, campaign: Campaign, war: War, legions: List[Legion]):
    legion_numerals = ["I", "II", "III", "IV", "V"]
    game.refresh_from_db()
    game.current_proposal = (
        f"Recall {proconsul.display_name} and {len(legions)} legions "
        f"({', '.join(legion_numerals[:len(legions)])}) from {campaign.display_name} in the {war.name}"
    )
    game.votes_yea = 15
    game.save()
    for faction in game.factions.all():
        faction.add_status_item(FactionStatusItem.DONE)
        faction.save()
    execute_effects_and_manage_actions(game.id, FakeRandomResolver())


def _setup_replace(game: Game):
    proconsul = Senator.objects.get(game=game, family_name="Julius")
    proconsul.add_title(Senator.Title.PROCONSUL)
    proconsul.location = "Sicilia"
    proconsul.save()

    field_consul = Senator.objects.get(game=game, family_name="Fabius")
    field_consul.add_title(Senator.Title.FIELD_CONSUL)
    field_consul.location = "Rome"
    field_consul.save()

    war = War.objects.create(
        game=game,
        name="1st Punic War",
        series_name="Punic",
        index=0,
        land_strength=10,
        fleet_support=5,
        naval_strength=0,
        disaster_numbers=[13],
        standoff_numbers=[11, 14],
        spoils=35,
        location="Sicilia",
        status=War.Status.ACTIVE,
    )
    return proconsul, field_consul, war


def _setup_pass_replace_proposal(game: Game, proconsul: Senator, field_consul: Senator, war: War, recently_deployed: bool = False, recently_reinforced: bool = False) -> Campaign:
    campaign = Campaign.objects.create(
        game=game,
        commander=proconsul,
        war=war,
        recently_deployed=recently_deployed,
        recently_reinforced=recently_reinforced,
    )
    game.refresh_from_db()
    game.current_proposal = f"Replace {proconsul.display_name} with {field_consul.display_name} in the {war.name}"
    game.votes_yea = 15
    game.save()
    for faction in game.factions.all():
        faction.add_status_item(FactionStatusItem.DONE)
        faction.save()
    resolver = FakeRandomResolver()
    execute_effects_and_manage_actions(game.id, resolver)
    return campaign


@pytest.mark.django_db
def test_recently_deployed_campaign_cannot_be_recalled(proconsul_campaign: Game):
    # Arrange
    game = proconsul_campaign
    proconsul = Senator.objects.get(game=game, family_name="Julius")
    war = War.objects.get(game=game, name="1st Punic War")

    legions = [Legion.objects.create(game=game, number=i) for i in range(1, 6)]
    campaign = Campaign.objects.get(game=game)
    campaign.recently_deployed = True
    campaign.save()
    for legion in legions:
        legion.campaign = campaign
        legion.save()

    # Act
    _setup_pass_recall_proposal(game, proconsul, campaign, war, legions)

    # Assert
    campaign.refresh_from_db()
    assert campaign.commander_id == proconsul.id


@pytest.mark.django_db
def test_recently_reinforced_campaign_cannot_be_recalled(proconsul_campaign: Game):
    # Arrange
    game = proconsul_campaign
    proconsul = Senator.objects.get(game=game, family_name="Julius")
    war = War.objects.get(game=game, name="1st Punic War")

    legions = [Legion.objects.create(game=game, number=i) for i in range(1, 6)]
    campaign = Campaign.objects.get(game=game)
    campaign.recently_reinforced = True
    campaign.save()
    for legion in legions:
        legion.campaign = campaign
        legion.save()

    # Act
    _setup_pass_recall_proposal(game, proconsul, campaign, war, legions)

    # Assert
    campaign.refresh_from_db()
    assert campaign.commander_id == proconsul.id


@pytest.mark.django_db
def test_new_commander_takes_over_campaign(senate_game: Game):
    # Arrange
    game = senate_game
    proconsul, field_consul, war = _setup_replace(game)

    # Act
    campaign = _setup_pass_replace_proposal(game, proconsul, field_consul, war)

    # Assert
    campaign.refresh_from_db()
    assert campaign.commander_id == field_consul.id


@pytest.mark.django_db
def test_replaced_proconsul_returns_to_rome(senate_game: Game):
    # Arrange
    game = senate_game
    proconsul, field_consul, war = _setup_replace(game)

    # Act
    _setup_pass_replace_proposal(game, proconsul, field_consul, war)

    # Assert
    proconsul.refresh_from_db()
    assert proconsul.location == "Rome"
    assert not proconsul.has_title(Senator.Title.PROCONSUL)


@pytest.mark.django_db
def test_recently_deployed_proconsul_cannot_be_replaced(senate_game: Game):
    # Arrange
    game = senate_game
    proconsul, field_consul, war = _setup_replace(game)

    # Act
    campaign = _setup_pass_replace_proposal(game, proconsul, field_consul, war, recently_deployed=True)

    # Assert
    campaign.refresh_from_db()
    assert campaign.commander_id == proconsul.id


@pytest.mark.django_db
def test_recently_reinforced_proconsul_cannot_be_replaced(senate_game: Game):
    # Arrange
    game = senate_game
    proconsul, field_consul, war = _setup_replace(game)

    # Act
    campaign = _setup_pass_replace_proposal(game, proconsul, field_consul, war, recently_reinforced=True)

    # Assert
    campaign.refresh_from_db()
    assert campaign.commander_id == proconsul.id


@pytest.mark.django_db
def test_replace_proconsul_not_available_when_commander_is_not_proconsul(senate_game: Game):
    # Arrange
    game = senate_game
    field_consul = Senator.objects.get(game=game, family_name="Fabius")
    field_consul.add_title(Senator.Title.FIELD_CONSUL)
    field_consul.location = "Sicilia"
    field_consul.save()

    war = War.objects.create(
        game=game,
        name="1st Punic War",
        series_name="Punic",
        index=0,
        land_strength=10,
        fleet_support=5,
        naval_strength=0,
        disaster_numbers=[13],
        standoff_numbers=[11, 14],
        spoils=35,
        location="Sicilia",
        status=War.Status.ACTIVE,
    )
    Campaign.objects.create(
        game=game,
        commander=field_consul,
        war=war,
        recently_deployed=False,
        recently_reinforced=False,
    )

    # Act
    execute_effects_and_manage_actions(game.id)

    # Assert
    action_names = [a.base_name for a in AvailableAction.objects.filter(game=game)]
    assert "Propose replacing proconsul" not in action_names


@pytest.mark.django_db
def test_senate_ends_when_presiding_magistrate_replaces_proconsul(
    proconsul_campaign: Game, resolver: FakeRandomResolver
):
    # Arrange
    game = proconsul_campaign
    campaign = Campaign.objects.get(game=game)
    proconsul = Senator.objects.get(game=game, family_name="Julius")
    proconsul.add_title(Senator.Title.PRIOR_CONSUL)
    proconsul.save()
    presiding_magistrate = Senator.objects.get(game=game, family_name="Cornelius")
    for i in range(1, 11):
        Legion.objects.create(game=game, number=i, campaign=campaign)
    for i in range(1, 6):
        Fleet.objects.create(game=game, number=i, campaign=campaign)

    field_consul = Senator.objects.get(game=game, family_name="Fabius")
    field_consul.add_title(Senator.Title.FIELD_CONSUL)
    field_consul.location = "Illyricum"
    field_consul.save()
    war = War.objects.create(
        game=game,
        name="1st Illyrian War",
        series_name="Illyrian",
        index=0,
        land_strength=5,
        fleet_support=3,
        naval_strength=0,
        disaster_numbers=[5],
        standoff_numbers=[17],
        spoils=10,
        famine=True,
        location="Illyricum",
        status=War.Status.ACTIVE,
    )
    field_campaign = Campaign.objects.create(game=game, war=war, commander=field_consul)
    for i in range(11, 17):
        Legion.objects.create(game=game, number=i, campaign=field_campaign)
    for i in range(6, 9):
        Fleet.objects.create(game=game, number=i, campaign=field_campaign)

    game.current_proposal = (
        f"Replace {proconsul.display_name} with {presiding_magistrate.display_name} "
        f"in the {campaign.war.name}"
    )
    game.votes_yea = 15
    game.save()
    for faction in game.factions.all():
        faction.add_status_item(FactionStatusItem.DONE)
        faction.save()
    resolver.dice_rolls = [18, 18]

    # Act
    execute_effects_and_manage_actions(game.id, resolver)

    # Assert
    game.refresh_from_db()
    presiding_magistrate.refresh_from_db()
    assert game.phase != Game.Phase.SENATE
    assert not presiding_magistrate.has_title(Senator.Title.PRESIDING_MAGISTRATE)
    assert not presiding_magistrate.has_title(Senator.Title.HRAO)


@pytest.mark.django_db
def test_replacement_below_enemy_strength_requires_incoming_commander_consent(
    senate_game: Game, resolver: FakeRandomResolver
):
    # Arrange
    game = senate_game
    proconsul, field_consul, war = _setup_replace(game)
    proconsul.add_title(Senator.Title.PRIOR_CONSUL)
    proconsul.save()
    campaign = Campaign.objects.create(
        game=game,
        war=war,
        commander=proconsul,
        recently_deployed=False,
        recently_reinforced=False,
    )
    Legion.objects.create(game=game, number=1, campaign=campaign)
    for i in range(1, 6):
        Fleet.objects.create(game=game, number=i, campaign=campaign)
    faction = field_consul.faction
    assert faction is not None

    # Act
    result = ProposeReplacingProconsulAction().execute(
        game_id=game.id,
        faction_id=faction.id,
        selection={
            "Campaign": str(campaign.id),
            "Replacement commander": str(field_consul.id),
        },
        random_resolver=resolver,
    )

    # Assert
    assert result.success
    field_consul.refresh_from_db()
    assert field_consul.has_status_item(Senator.StatusItem.CONSENT_REQUIRED)
