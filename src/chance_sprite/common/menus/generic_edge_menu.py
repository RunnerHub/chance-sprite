from __future__ import annotations

from typing import Callable

import discord
from discord import ui, ButtonStyle

from chance_sprite.common.common import Glitch
from chance_sprite.common.commonui import GenericResultAccessor
from chance_sprite.common.result_types.hits_result import HitsResult
from chance_sprite.common.modals.confirm_modal import ConfirmModal
from chance_sprite.common.modals.dice_input_modal import DiceInputModal
from chance_sprite.common.result_types.push_limit_result import PushTheLimitHitsResult
from chance_sprite.common.result_types.second_chance_result import SecondChanceHitsResult


class GenericEdgeMenu(ui.LayoutView):
    def __init__(self, title: str, result_accessor: GenericResultAccessor, is_authorized: Callable[[int], bool]):
        super().__init__(timeout=None)
        self.result_accessor = result_accessor
        self.is_authorized = is_authorized
        self.title = title
        self.edge_buttons = []
        self.followup_message = None
        self._build()

    def _build(self):
        container = ui.Container(accent_color=0xAAAA44)
        container.add_item(ui.TextDisplay(self.title))

        second_chance = ui.Button(style=ButtonStyle.grey, label="2nd Chance")
        push_limit = ui.Button(style=ButtonStyle.grey, label="Push Limit")
        close_call = ui.Button(style=ButtonStyle.grey, label="Close Call")
        second_chance.callback = self.do_nothing
        push_limit.callback = self.do_nothing
        close_call.callback = self.do_nothing

        result = self.result_accessor.get()

        # Not edged yet
        if type(result) is HitsResult:
            if (result.limit == 0 or result.dice_hits < result.limit) and result.dice_hits < result.dice:
                second_chance.callback = self.on_second_chance_button
                second_chance.style = ButtonStyle.primary

            push_limit.callback = self.on_push_limit_button
            push_limit.style = ButtonStyle.primary

            if result.glitch != Glitch.NONE:
                close_call.callback = self.on_close_call_button
                close_call.style = ButtonStyle.primary

        edge_action_row = ui.ActionRow(second_chance, push_limit, close_call)
        container.add_item(edge_action_row)
        self.edge_buttons = [second_chance, push_limit, close_call]

        adjust = ui.Button(style=ButtonStyle.primary, label="Adjust Roll")
        adjust.callback = self.on_adjust_dice_button

        dismiss = ui.Button(style=ButtonStyle.danger, label="Dismiss")
        dismiss.callback = self.on_dismiss_button

        adjust_action_row = ui.ActionRow(adjust, dismiss)
        container.add_item(adjust_action_row)

        self.add_item(container)

    async def handle_case(self, mutate: Callable[[HitsResult], HitsResult], interaction: discord.Interaction):
        if not self.is_authorized(interaction.user.id):
            return
        await self.result_accessor.update(mutate(self.result_accessor.get()))

    async def on_second_chance_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ConfirmModal(
                title="Confirm: 2nd Chance",
                body="## Are you sure you want to use Edge to reroll failures?",
                do_action=self.on_second_chance_confirm,
                on_after=self._after_use,
            )
        )

    async def on_second_chance_confirm(self, interaction: discord.Interaction):
        await self.handle_case(lambda r : SecondChanceHitsResult.from_hitsresult(r), interaction)
        self.disable_edge_buttons()

    async def on_push_limit_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            DiceInputModal(
                title="Confirm: Push the Limit",
                body="Enter your edge score to roll exploding dice",
                do_action=self.on_push_limit_confirm,
                on_after=self._after_use,
            )
        )

    async def on_push_limit_confirm(self, interaction: discord.Interaction, edge: int) -> None:
        await self.handle_case(lambda r : PushTheLimitHitsResult.from_hits_result(r, edge), interaction)
        self.disable_edge_buttons()

    async def on_close_call_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ConfirmModal(
                title="Confirm: Close Call",
                body="## Are you sure you want to use Edge to mitigate a glitch?",
                do_action=self.on_close_call_confirm,
                on_after=self._after_use,
            )
        )

    async def on_close_call_confirm(self, interaction: discord.Interaction) -> None:
        await self.handle_case(lambda r : r.close_call(), interaction)
        self.disable_edge_buttons()

    async def on_adjust_dice_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            DiceInputModal(
                title="Adjust dice",
                body="WIP", #"Did you make a mistake in calculating modifiers? You can change the dice score here.",
                do_action=self.on_adjust_dice_confirm,
                on_after=self._after_use,
                min_val=-99,
                max_val=99,
            )
        )

    async def on_adjust_dice_confirm(self, interaction: discord.Interaction, dice: int) -> None:
        await self.handle_case(lambda r : r.adjust_dice(dice), interaction)

    async def on_dismiss_button(self, interaction: discord.Interaction):
        if self.followup_message:
            await self.followup_message.delete()

    async def _after_use(self, interaction: discord.Interaction=None):
        if self.followup_message:
            await self.followup_message.edit(view=self)
        if interaction:
            await interaction.response.defer()

    def disable_edge_buttons(self):
        for button in self.edge_buttons:
            button.style = ButtonStyle.grey
            button.callback = self.do_nothing

    async def do_nothing(self, interaction: discord.Interaction):
        await interaction.response.defer()
