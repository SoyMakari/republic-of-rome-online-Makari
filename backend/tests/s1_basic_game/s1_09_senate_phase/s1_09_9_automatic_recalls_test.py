import pytest
from rorapp.classes.faction_status_item import FactionStatusItem
from rorapp.classes.random_resolver import FakeRandomResolver
from rorapp.models.fleet import Fleet
from rorapp.models.senator import Senator
from rorapp.helpers.unit_lists import unit_list_to_string
from rorapp.models import Campaign, Game, Legion, War
from rorapp.effects.meta.effect_executor import execute_effects_and_manage_actions


@pytest.mark.django_db
def test_commanderless_campaign_recalled_at_senate_close(basic_game: Game, resolver: FakeRandomResolver):
    # Arrange
    game = basic_game
    game.phase = Game.Phase.SENATE
    game.sub_phase = Game.SubPhase.END
    game.save()

    war = War.objects.create(
        game=game,
        name="1st Punic War",
        series_name="Punic",
        index=0,
        land_strength=10,
        fleet_support=0,
        naval_strength=0,
        disaster_numbers=[],
        standoff_numbers=[],
        spoils=35,
        location="Sicilia",
        status=War.Status.ACTIVE,
    )
    campaign = Campaign.objects.create(game=game, war=war, commander=None)
    for i in range(1, 5):
        Legion.objects.create(game=game, number=i, campaign=campaign)

    # Act
    execute_effects_and_manage_actions(game.id, resolver)

    # Assert
    assert Campaign.objects.filter(game=game).count() == 0
    assert Legion.objects.filter(game=game, campaign__isnull=False).count() == 0


@pytest.mark.django_db
def test_fleet_only_proconsul_returns_by_senate_close_after_all_fleets_recalled(
    proconsul_campaign: Game, resolver: FakeRandomResolver
):
    # Arrange
    game = proconsul_campaign
    proconsul = Senator.objects.get(game=game, family_name="Julius")
    proconsul.add_title(Senator.Title.PRIOR_CONSUL)
    proconsul.save()
    campaign = Campaign.objects.get(game=game)
    war = campaign.war
    war.naval_strength = 10
    war.save()
    fleets = [
        Fleet.objects.create(game=game, number=i, campaign=campaign)
        for i in range(1, 4)
    ]
    game.current_proposal = (
        f"Recall {unit_list_to_string([], fleets)} from {campaign.display_name} "
        f"in the {war.name}"
    )
    game.votes_yea = 15
    game.save()
    for faction in game.factions.all():
        faction.add_status_item(FactionStatusItem.DONE)
        faction.save()
    execute_effects_and_manage_actions(game.id, resolver)

    game.refresh_from_db()
    game.sub_phase = Game.SubPhase.END
    game.save()
    presiding_magistrate = Senator.objects.get(game=game, family_name="Cornelius")
    presiding_magistrate.remove_title(Senator.Title.PRESIDING_MAGISTRATE)
    presiding_magistrate.save()

    # Act
    execute_effects_and_manage_actions(game.id, resolver)

    # Assert
    proconsul.refresh_from_db()
    assert proconsul.location == "Rome"
    assert not proconsul.has_title(Senator.Title.PROCONSUL)
