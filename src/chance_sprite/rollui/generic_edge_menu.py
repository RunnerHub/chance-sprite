from __future__ import annotations

from typing import Callable

from discord import ui, WebhookMessage, Interaction, ButtonStyle

from chance_sprite.result_types import Glitch
from chance_sprite.result_types.hits_result import HitsResult
from chance_sprite.roller import second_chance, push_the_limit, close_call
from chance_sprite.rollui.commonui import GenericResultAccessor
from chance_sprite.rollui.confirm_modal import ConfirmModal
from chance_sprite.rollui.dice_input_modal import NumberInputModal
from chance_sprite.rollui.my_button import ModalButton, RedButton
from chance_sprite.sprite_context import InteractionContext, ClientContext


class EdgeButton(ui.Button):
    def __init__(self, label: str, result_accessor: GenericResultAccessor, original_message_id: int):
        super().__init__(label=label)
        self.result_accessor = result_accessor
        self.original_message_id = original_message_id
        self.base_view: GenericEdgeMenu | None = None
        self.callback = self.on_click
        self.style = ButtonStyle.primary

    def disable_edge_buttons(self):
        if self.base_view is GenericEdgeMenu:
            self.base_view.disable_edge_buttons()

    async def _after_use(self, interaction: Interaction[ClientContext]):
        if self.base_view and self.base_view.followup_message:
            await self.base_view.followup_message.edit(view=self.base_view)
        if interaction:
            await InteractionContext(interaction).interaction.response.defer()

    def on_click(self, interaction: Interaction[ClientContext]):
        pass


class SecondChanceButton(EdgeButton):
    def __init__(self, result_accessor: GenericResultAccessor, original_message_id: int):
        super().__init__(label="2nd Chance", result_accessor=result_accessor, original_message_id=original_message_id)

    async def on_second_chance_confirm(self, interaction: Interaction[ClientContext]):
        await self.base_view.handle_case(lambda r: second_chance(r), interaction)
        self.disable_edge_buttons()

    async def on_click(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            ConfirmModal(
                title="2nd Chance",
                body="## Are you sure you want to use Edge to reroll failures?",
                do_action=self.on_second_chance_confirm,
                on_after=self._after_use,
            )
        )


class PushLimitButton(EdgeButton):
    def __init__(self, result_accessor: GenericResultAccessor, original_message_id: int):
        super().__init__(label="Push the Limit", result_accessor=result_accessor,
                         original_message_id=original_message_id)

    async def on_push_limit_confirm(self, interaction: Interaction[ClientContext], edge: int) -> None:
        await self.base_view.handle_case(lambda r: push_the_limit(r, edge), interaction)
        self.disable_edge_buttons()

    async def on_click(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            NumberInputModal(
                title="Push the Limit",
                body="Eter your edge score to roll exploding dice",
                do_action=self.on_push_limit_confirm,
                on_after=self._after_use,
            )
        )


class CloseCallButton(EdgeButton):
    def __init__(self, result_accessor: GenericResultAccessor, original_message_id: int):
        super().__init__(label="Close Call", result_accessor=result_accessor, original_message_id=original_message_id)

    async def on_close_call_confirm(self, interaction: Interaction[ClientContext]) -> None:
        await self.base_view.handle_case(lambda r: close_call(r), interaction)
        self.disable_edge_buttons()

    async def on_click(self, interaction: Interaction[ClientContext]):
        await interaction.response.send_modal(
            ConfirmModal(
                title="Close Call",
                body="## Are you sure you want to use Edge to mitigate a glitch?",
                do_action=self.on_close_call_confirm,
                on_after=self._after_use,
            )
        )


class EdgeButtonRow(ui.ActionRow):
    def __init__(self, result_accessor: GenericResultAccessor, original_message_id: int):
        self.second_chance = SecondChanceButton(result_accessor, original_message_id)
        self.push_limit = PushLimitButton(result_accessor, original_message_id)
        self.close_call = CloseCallButton(result_accessor, original_message_id)
        super().__init__(self.second_chance, self.push_limit, self.close_call, )

    def disable_edge_buttons(self):
        for child in self.walk_children():
            if isinstance(child, ModalButton):
                child.disabled = True

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

        self.edge_action_row = EdgeButtonRow(result_accessor, original_message_id)
        self.edge_action_row.second_chance.base_view = self
        self.edge_action_row.push_limit.base_view = self
        self.edge_action_row.close_call.base_view = self
        container.add_item(self.edge_action_row)

        result = self.get_result(context)

        # Already Edged
        if not type(result) is HitsResult:
            self.edge_action_row.second_chance.disabled = True
            self.edge_action_row.push_limit.disabled = True
            self.edge_action_row.close_call.disabled = True

        # Limit already hit
        if result.limit_reached:
            self.edge_action_row.second_chance.disabled = True

        # No glitch to negate
        if result.glitch == Glitch.NONE:
            self.edge_action_row.close_call.disabled = True

        # self.edge_action_row = ui.ActionRow(second_chance_button, push_limit_button, close_call_button)

        adjust_dice = ModalButton(
            NumberInputModal(
                title="Adjust dice",
                body="Adjust dice pool ±. Rolls are kept.",
                do_action=self.on_adjust_dice_confirm,
                on_after=self._after_use,
                min_val=-99,
                max_val=99,
            )
        )

        adjust_limit = ModalButton(
            NumberInputModal(
                title="Adjust limit",
                body="You can set the limit directly here.",
                do_action=self.on_adjust_limit_confirm,
                on_after=self._after_use,
                min_val=0,
                max_val=99,
            )
        )

        dismiss = RedButton("Dismiss", self.on_dismiss_button)

        adjust_action_row = ui.ActionRow(adjust_dice, adjust_limit, dismiss)
        container.add_item(adjust_action_row)

        self.add_item(container)

    def original_message(self, interaction: Interaction[ClientContext]):
        return interaction.client.message_cache[self.original_message_id]

    def get_result(self, context: InteractionContext):
        original_message = self.original_message(context.interaction)
        return self.result_accessor.get(original_message)

    async def set_result(self, new_result, interaction: Interaction[ClientContext]):
        await InteractionContext(interaction).update_message(self.original_message(interaction), new_result)

    async def handle_case(self, mutate: Callable[[HitsResult], HitsResult], interaction: Interaction[ClientContext]):
        context = InteractionContext(interaction)
        if not self.original_message(interaction).owner_id == interaction.user.id:
            return
        old_result = self.get_result(context)
        new_result = self.result_accessor.update(self.original_message(interaction), mutate(old_result))
        await self.set_result(new_result, interaction)

    async def on_second_chance_confirm(self, interaction: Interaction[ClientContext]):
        await self.handle_case(lambda r: second_chance(r), interaction)
        self.disable_edge_buttons()

    async def on_push_limit_confirm(self, interaction: Interaction[ClientContext], edge: int) -> None:
        await self.handle_case(lambda r: push_the_limit(r, edge), interaction)
        self.disable_edge_buttons()

    async def on_close_call_confirm(self, interaction: Interaction[ClientContext]) -> None:
        await self.handle_case(lambda r: close_call(r), interaction)
        self.disable_edge_buttons()

    async def on_adjust_dice_confirm(self, interaction: Interaction[ClientContext], dice: int) -> None:
        await self.handle_case(lambda r: r.adjust_dice(dice), interaction)

    async def on_adjust_limit_confirm(self, interaction: Interaction[ClientContext], limit: int) -> None:
        await self.handle_case(lambda r: r.adjust_limit(limit), interaction)

    async def on_dismiss_button(self, interaction: Interaction[ClientContext]):
        if self.followup_message:
            await self.followup_message.delete()

    async def _after_use(self, interaction: Interaction[ClientContext] | None = None):
        if self.followup_message:
            await self.followup_message.edit(view=self)
        if interaction:
            await InteractionContext(interaction).interaction.response.defer()

    def disable_edge_buttons(self):
        for child in self.walk_children():
            if child is ModalButton:
                child.disabled = True
