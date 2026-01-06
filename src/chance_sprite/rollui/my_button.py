from typing import Callable, Coroutine

import discord
from discord import ButtonStyle, Interaction
from discord import ui

from chance_sprite.sprite_context import ClientContext, InteractionContext


class MyButton(ui.Button):
    def __init__(self, label: str, callback: Callable[[discord.Interaction[ClientContext]], Coroutine] = None):
        super().__init__(label=label)
        if callback:
            self.callback = callback
            self.style = ButtonStyle.primary
        else:
            self.callback = self.do_nothing
            self.style = ButtonStyle.secondary

    def enable(self, callback: Callable[[discord.Interaction[ClientContext]], Coroutine]):
        self.callback = callback
        self.style = ButtonStyle.primary

    def disable(self):
        self.callback = self.do_nothing
        self.style = ButtonStyle.secondary

    @staticmethod
    async def do_nothing(interaction: Interaction[ClientContext]):
        await interaction.response.defer()


class ModalButton(MyButton):
    def __init__(self, modal: ui.Modal, label=""):
        if not label:
            label = modal.title

        async def on_click(interaction: Interaction[ClientContext]):
            await InteractionContext(interaction).interaction.response.send_modal(modal)

        super().__init__(label, on_click)


class RedButton(MyButton):
    def __init__(self, label: str, callback: Callable[[discord.Interaction[ClientContext]], Coroutine] = None):
        super().__init__(label=label, callback=callback)
        self.style = ButtonStyle.danger
