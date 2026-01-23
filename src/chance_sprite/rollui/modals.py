from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import Interaction, ui

from chance_sprite.rollui.modal_inputs import ValidLabel
from chance_sprite.sprite_context import InteractionContext

if TYPE_CHECKING:
    from chance_sprite.rollui.base_menu_view import BaseMenuView



class BuiltModal(ui.Modal):
    def __init__(
        self,
        title: str,
        *,
        body: str | None,
        fields: list[ValidLabel[Any]],
        menu_view: "BaseMenuView | None",
        original_view_id: int,
        transform,
        on_fail=None,
    ):
        super().__init__(title=title, timeout=None)
        self._view = menu_view
        self._transform = transform
        self._fields = fields
        self._origin_id = original_view_id
        self._on_fail = on_fail

        if body is not None:
            self.add_item(ui.TextDisplay(body))
        for f in fields:
            self.add_item(f)

    async def on_submit(self, interaction: Interaction):
        try:
            values = [f.validate() for f in self._fields]
        except ValueError as e:
            await interaction.response.send_message(
                str(e), ephemeral=True, delete_after=5
            )
            return

        context = InteractionContext(interaction)

        record = context.get_cached_record(self._origin_id)

        new_record = self._transform(record.roll_result, context, *values)
        try:
            await context.update_original(record, new_record)
        except Exception:
            if self._on_fail:
                await self._on_fail(record, context, *values)

        if self._view:
            await context.update_menu(self._view)
