from __future__ import annotations

import logging
from typing import Callable, override

from discord import ui, WebhookMessage, Interaction, ButtonStyle

from chance_sprite.result_types import Glitch
from chance_sprite.result_types.hits_result import HitsResult
from chance_sprite.roller import second_chance, push_the_limit, close_call
from chance_sprite.rollui.commonui import GenericResultAccessor
from chance_sprite.rollui.modals import NumberInputModal, ConfirmModal
from chance_sprite.sprite_context import InteractionContext, ClientContext

log = logging.getLogger(__name__)


class EdgeButton(ui.Button):
    def __init__(self, label: str):
        super().__init__(label=label)
        self.base_view: GenericEdgeMenu | None = None
        self.style = ButtonStyle.primary

    def disable_edge_buttons(self):
        if self.base_view:
            self.base_view.disable_edge_buttons()



class SecondChanceButton(EdgeButton):
    def __init__(self):
        super().__init__(label="2nd Chance")

    async def on_second_chance_confirm(self, interaction: Interaction[ClientContext]):
        await self.base_view.handle_case(lambda r: second_chance(r), interaction)
        self.disable_edge_buttons()

    @override
    async def callback(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            ConfirmModal(
                title="2nd Chance",
                body="## Are you sure you want to use Edge to reroll failures?",
                do_action=self.on_second_chance_confirm,
                on_after=self.base_view.after_use,
            )
        )


class PushLimitButton(EdgeButton):
    def __init__(self):
        super().__init__(label="Push the Limit")

    async def on_push_limit_confirm(self, interaction: Interaction[ClientContext], edge: int) -> None:
        await self.base_view.handle_case(lambda r: push_the_limit(r, edge), interaction)
        self.disable_edge_buttons()

    @override
    async def callback(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            NumberInputModal(
                title=self.label,
                body="Enter your edge score to roll exploding dice",
                do_action=self.on_push_limit_confirm,
                on_after=self.base_view.after_use,
            )
        )


class CloseCallButton(EdgeButton):
    def __init__(self):
        super().__init__(label="Close Call")

    async def on_close_call_confirm(self, interaction: Interaction[ClientContext]) -> None:
        await self.base_view.handle_case(lambda r: close_call(r), interaction)
        self.disable_edge_buttons()

    @override
    async def callback(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            ConfirmModal(
                title=self.label,
                body="## Are you sure you want to use Edge to mitigate a glitch?",
                do_action=self.on_close_call_confirm,
                on_after=self.base_view.after_use,
            )
        )


class AdjustButton(ui.Button):
    def __init__(self, label: str):
        super().__init__(label=label)
        self.base_view: GenericEdgeMenu | None = None
        self.style = ButtonStyle.primary


class AdjustDiceButton(AdjustButton):
    def __init__(self):
        super().__init__(label="Adjust Dice")

    async def on_adjust_dice_confirm(self, interaction: Interaction[ClientContext], dice: int) -> None:
        await self.base_view.handle_case(lambda r: r.adjust_dice(dice), interaction)

    @override
    async def callback(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            NumberInputModal(
                title=self.label,
                body="Adjust dice pool ±. Rolls are kept.",
                do_action=self.on_adjust_dice_confirm,
                on_after=self.base_view.after_use,
                min_val=-99,
                max_val=99,
            )
        )


class AdjustLimitButton(AdjustButton):
    def __init__(self):
        super().__init__(label="Adjust Limit")

    async def on_adjust_limit_confirm(self, interaction: Interaction[ClientContext], limit: int) -> None:
        await self.base_view.handle_case(lambda r: r.adjust_limit(limit), interaction)

    @override
    async def callback(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            NumberInputModal(
                title=self.label,
                body="You can set the limit directly here.",
                do_action=self.on_adjust_limit_confirm,
                on_after=self.base_view.after_use,
                min_val=0,
                max_val=99,
            )
        )

class GenericEdgeMenu(ui.LayoutView):
    def __init__(self, title: str, result_accessor: GenericResultAccessor, original_message_id: int,
                 context: InteractionContext):
        super().__init__(timeout=None)
        self.result_accessor = result_accessor
        self.original_message_id = original_message_id
        self.title = title
        self.followup_message: WebhookMessage | None = None
        self.edge_action_row = None

        container = ui.Container(accent_color=0xAAAA44)
        container.add_item(ui.TextDisplay(self.title))

        second_chance_button = SecondChanceButton()
        second_chance_button.base_view = self
        push_limit_button = PushLimitButton()
        push_limit_button.base_view = self
        close_call_button = CloseCallButton()
        close_call_button.base_view = self

        self.edge_action_row = ui.ActionRow(second_chance_button, push_limit_button, close_call_button)
        container.add_item(self.edge_action_row)

        original_message = context.get_cached_record(self.original_message_id)
        result = self.result_accessor.get(original_message)

        # Already Edged
        if not type(result) is HitsResult:
            self.disable_edge_buttons()

        # Limit already hit
        if result.limit_reached:
            second_chance_button.disabled = True

        # No glitch to negate
        if result.glitch == Glitch.NONE:
            close_call_button.disabled = True

        # self.edge_action_row = ui.ActionRow(second_chance_button, push_limit_button, close_call_button)
        adjust_dice = AdjustDiceButton()
        adjust_dice.base_view = self
        adjust_limit = AdjustLimitButton()
        adjust_limit.base_view = self
        dismiss = ui.Button(label="Dismiss", style=ButtonStyle.danger)
        dismiss.callback = self.on_dismiss_button

        adjust_action_row = ui.ActionRow(adjust_dice, adjust_limit, dismiss)
        container.add_item(adjust_action_row)

        self.add_item(container)

    async def handle_case(self, mutate: Callable[[HitsResult], HitsResult], interaction: Interaction[ClientContext]):
        context = InteractionContext(interaction)
        original_message = context.get_cached_record(self.original_message_id)
        if not original_message.owner_id == context.interaction.user.id:
            return
        old_result = self.result_accessor.get(original_message)
        new_result = self.result_accessor.update(original_message, mutate(old_result))
        await context.update_original(original_message, new_result)
        log.info(f"original message updated.")

    async def on_dismiss_button(self, interaction: Interaction[ClientContext]):
        if self.followup_message:
            await InteractionContext(interaction).defer_if_needed()
            await self.followup_message.delete()

    async def after_use(self, interaction: Interaction[ClientContext] | None = None):
        if self.followup_message:
            await self.followup_message.edit(view=self)
        if interaction:
            await InteractionContext(interaction).defer_if_needed()

    def disable_edge_buttons(self):
        for child in self.edge_action_row.walk_children():
            if isinstance(child, EdgeButton):
                child.disabled = True
                child.style = ButtonStyle.grey
