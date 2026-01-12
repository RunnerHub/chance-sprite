from __future__ import annotations

from discord import ui, Interaction

from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import ResistableRoll
from chance_sprite.sprite_context import InteractionContext


class NumberInputModal(ui.Modal):
    def __init__(
        self,
        title: str,
        body: str,
        *,
        do_action,
        on_after,
        min_val: int = 0,
        max_val: int = 99,
    ):
        super().__init__(title=title, timeout=None)
        self._do_action = do_action  # async (context, extra_dice:int) -> None
        self._on_after = on_after  # async (context) -> None
        self.dice_to_add: ui.TextInput = ui.TextInput(
            placeholder="e.g. 3",
            required=True,
            min_length=1,
            max_length=3,
        )
        self.label = ui.Label(
            text=body, component=self.dice_to_add, description="Description"
        )
        self.min_val = min_val
        self.max_val = max_val
        self.add_item(self.label)

    async def on_submit(self, interaction: Interaction) -> None:
        raw = str(self.dice_to_add.value).strip()
        try:
            extra = int(raw)
        except ValueError:
            await interaction.response.send_message(
                "That isn’t a number.", ephemeral=True, delete_after=5
            )
            return

        if extra < self.min_val or extra > self.max_val:
            await interaction.response.send_message(
                f"Pick a number between {self.min_val} and {self.max_val}.",
                ephemeral=True,
                delete_after=5,
            )
            return

        await self._do_action(interaction, extra)
        await self._on_after(interaction)


class ConfirmModal(ui.Modal):
    def __init__(self, title: str, *, body: str, do_action, on_after):
        super().__init__(title=title, timeout=None)
        self._do_action = do_action  # async (context) -> None
        self._on_after = on_after  # async (context) -> None
        confirm: ui.TextDisplay = ui.TextDisplay(body)
        self.add_item(confirm)

    async def on_submit(self, context: Interaction) -> None:
        await self._do_action(context)
        await self._on_after(context)


class ResistModal(NumberInputModal):
    def __init__(self, record: MessageRecord, *, min_val: int = 0, max_val: int = 99):
        if isinstance(record.roll_result, ResistableRoll):
            self.threshold = record.roll_result.resistance_target()
        else:
            self.threshold = 0
        super().__init__(
            title=f"Resist {record.label} ({self.threshold})?",
            body="Enter your resistance dice pool.",
            do_action=self.on_resist_confirm,
            on_after=self.after_use,
            min_val=min_val,
            max_val=max_val,
        )
        self.record = record

    async def on_resist_confirm(self, interaction: Interaction, dice: int):
        context = InteractionContext(interaction)
        from chance_sprite.roll_types.basic import ThresholdRoll, roll_simple

        threshold_roll: ThresholdRoll = roll_simple(
            dice=dice, threshold=self.threshold, limit=0
        )
        updated_record = context.message_store.get(self.record.message_id)
        if updated_record:
            self.record = updated_record
        await context.transmit_result(
            f"Resisting {self.record.label} ({self.threshold})", threshold_roll
        )

    async def after_use(self, interaction: Interaction):
        context = InteractionContext(interaction)
        await context.defer_if_needed()
