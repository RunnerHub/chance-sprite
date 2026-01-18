from __future__ import annotations

from discord import Interaction, ui
from discord.utils import MISSING

from chance_sprite.message_cache.message_record import MessageRecord
from chance_sprite.message_cache.roll_record_base import ResistableRoll
from chance_sprite.sprite_context import InteractionContext


class NumberInputField(ui.TextInput):
    def __init__(
        self,
        *,
        custom_id: str | None = None,
        placeholder: str = "e.g. 3",
        default: str | None = None,
        required: bool = True,
        min_value: int,
        max_value: int,
    ) -> None:
        max_length = max(len(f"{min_value:+}"), len(f"{max_value:+}"))
        super().__init__(
            custom_id=custom_id or MISSING,
            placeholder=placeholder,
            default=default,
            required=required,
            min_length=1,
            max_length=max_length,
        )
        self.min_value = min_value
        self.max_value = max_value

    def validate(self):
        raw = str(self.value).strip()
        input = int(raw)
        if input < self.min_value or input > self.max_value:
            raise ValueError(
                f"Pick a number between {self.min_value} and {self.max_value}."
            )
        return input


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
        self.dice_to_add: NumberInputField = NumberInputField(
            required=True,
            min_value=min_val,
            max_value=max_val,
        )
        self.label = ui.Label(
            text=body,
            component=self.dice_to_add,
            description="Enter the number of dice",
        )
        self.add_item(self.label)

    async def on_submit(self, interaction: Interaction) -> None:
        try:
            extra = self.dice_to_add.validate()
        except ValueError as e:
            await interaction.response.send_message(
                str(e), ephemeral=True, delete_after=5
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
            title="Resistance roll",
            body=f"Rolling to resist {record.label} ({self.threshold} hits)",
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
        updated_record = context.get_cached_record(self.record.message_id)
        if updated_record:
            self.record = updated_record
        await context.transmit_result(
            f"Resisting {self.record.label} ({self.threshold})", threshold_roll
        )

    async def after_use(self, interaction: Interaction):
        context = InteractionContext(interaction)
        await context.defer_if_needed()


class InPlaceResistModal(NumberInputModal):
    def __init__(self, record: MessageRecord, *, min_val: int = 0, max_val: int = 99):
        if isinstance(record.roll_result, ResistableRoll):
            self.threshold = record.roll_result.resistance_target()
        else:
            self.threshold = 0
        super().__init__(
            title="Resistance roll",
            body=f"Rolling to resist {record.label} ({self.threshold} hits)",
            do_action=self.on_resist_confirm,
            on_after=self.after_use,
            min_val=min_val,
            max_val=max_val,
        )
        self.record_id = record.message_id

    async def on_resist_confirm(self, interaction: Interaction, dice: int):
        context = InteractionContext(interaction)
        record = context.get_cached_record(self.record_id)
        if not record:
            raise Exception("TODO")
        from chance_sprite.roll_types.basic import ThresholdRoll, roll_simple

        if (
            isinstance(record.roll_result, ResistableRoll)
            and len(record.roll_result.already_resisted()) < 10
        ):
            resisted_record = record.roll_result.resist(record, context, dice)
            await context.update_original(record, resisted_record)

        else:
            threshold_roll: ThresholdRoll = roll_simple(
                dice=dice, threshold=self.threshold, limit=0
            )
            await context.transmit_result(
                f"Resisting {record.label} ({self.threshold})", threshold_roll
            )

    async def after_use(self, interaction: Interaction):
        context = InteractionContext(interaction)
        await context.defer_if_needed()
