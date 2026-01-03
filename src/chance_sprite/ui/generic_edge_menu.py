from __future__ import annotations

from typing import Callable

import discord
from discord import ui, ButtonStyle, WebhookMessage

from chance_sprite.discord_sprite import SpriteContext
from chance_sprite.message_cache.roll_record import MessageRecord
from chance_sprite.result_types import Glitch
from chance_sprite.result_types.close_call_result import CloseCallResult
from chance_sprite.result_types.hits_result import HitsResult
from chance_sprite.result_types.push_limit_result import PushTheLimitHitsResult
from chance_sprite.result_types.second_chance_result import SecondChanceHitsResult
from chance_sprite.ui.commonui import GenericResultAccessor
from chance_sprite.ui.confirm_modal import ConfirmModal
from chance_sprite.ui.dice_input_modal import DiceInputModal


class GenericEdgeMenu(ui.LayoutView):
    def __init__(self, title: str, result_accessor: GenericResultAccessor, original_message: MessageRecord,
                 context: SpriteContext):
        super().__init__(timeout=None)
        self.result_accessor = result_accessor
        self.original_message = original_message
        self.title = title
        self.context = context
        self.edge_buttons: list[ui.Button] = []
        self.followup_message: WebhookMessage | None = None
        self._build()

    def get_result(self):
        self.original_message = self.context.message_cache[self.original_message.message_id]
        return self.result_accessor.get(self.original_message)

    async def set_result(self, new_result, interaction: discord.Interaction):
        new_record = await self.context.update_message(self.original_message, new_result, interaction)
        self.original_message = new_record

    async def send_as_followup(self, interaction: discord.Interaction):
        self.followup_message = await interaction.followup.send(view=self, ephemeral=True, wait=True)


    def _build(self):
        container = ui.Container(accent_color=0xAAAA44)
        container.add_item(ui.TextDisplay(self.title))

        second_chance = ui.Button(style=ButtonStyle.grey, label="2nd Chance")
        push_limit = ui.Button(style=ButtonStyle.grey, label="Push Limit")
        close_call = ui.Button(style=ButtonStyle.grey, label="Close Call")
        second_chance.callback = self.do_nothing
        push_limit.callback = self.do_nothing
        close_call.callback = self.do_nothing

        result = self.get_result()

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

        adjust_dice = ui.Button(style=ButtonStyle.primary, label="Adjust Roll")
        adjust_dice.callback = self.on_adjust_dice_button

        adjust_limit = ui.Button(style=ButtonStyle.primary, label="Adjust Limit")
        adjust_limit.callback = self.on_adjust_limit_button

        dismiss = ui.Button(style=ButtonStyle.danger, label="Dismiss")
        dismiss.callback = self.on_dismiss_button

        adjust_action_row = ui.ActionRow(adjust_dice, adjust_limit, dismiss)
        container.add_item(adjust_action_row)

        self.add_item(container)

    async def handle_case(self, mutate: Callable[[HitsResult], HitsResult], interaction: discord.Interaction):
        if not self.original_message.owner_id == interaction.user.id:
            return
        old_result = self.get_result()
        new_result = self.result_accessor.update(self.original_message, mutate(old_result))
        await self.set_result(new_result, interaction)

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
        await self.handle_case(lambda r : CloseCallResult.from_hitsresult(r), interaction)
        self.disable_edge_buttons()

    async def on_adjust_dice_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            DiceInputModal(
                title="Adjust dice",
                body="Adjust dice pool ±. Rolls are kept.",
                do_action=self.on_adjust_dice_confirm,
                on_after=self._after_use,
                min_val=-99,
                max_val=99,
            )
        )

    async def on_adjust_dice_confirm(self, interaction: discord.Interaction, dice: int) -> None:
        await self.handle_case(lambda r : r.adjust_dice(dice), interaction)

    async def on_adjust_limit_button(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            DiceInputModal(
                title="Adjust limit",
                body="You can set the limit directly here.",
                do_action=self.on_adjust_limit_confirm,
                on_after=self._after_use,
                min_val=0,
                max_val=99,
            )
        )

    async def on_adjust_limit_confirm(self, interaction: discord.Interaction, limit: int) -> None:
        await self.handle_case(lambda r: r.adjust_limit(limit), interaction)

    async def on_dismiss_button(self, interaction: discord.Interaction):
        if self.followup_message:
            await self.followup_message.delete()

    async def _after_use(self, interaction: discord.Interaction | None = None):
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
