from discord import SelectOption, ui
from discord.utils import MISSING


class ValidLabel[T](ui.Label):
    def validate(self) -> T: ...


class LabeledNumberField(ValidLabel):
    def __init__(
        self,
        label: str,
        min_value: int,
        max_value: int,
        *,
        placeholder: str = "e.g. 3",
        default: str | None = None,
        required: bool = True,
    ):
        self.input = ui.TextInput(
            placeholder=placeholder,
            default=default,
            required=required,
            min_length=1,
            max_length=max(
                len(f"{min_value:+}"),
                len(f"{max_value:+}"),
            ),
        )
        super().__init__(text=label, component=self.input)
        self.min_value = min_value
        self.max_value = max_value

    def validate(self) -> int:
        raw = str(self.input.value).strip()
        if not raw and not self.input.required:
            return 0
        value = int(raw)
        if value < self.min_value or value > self.max_value:
            raise ValueError(
                f"Pick a number between {self.min_value} and {self.max_value}."
            )
        return value


class LabeledBooleanField(ValidLabel):
    def __init__(
        self,
        label: str,
        *,
        custom_id: str | None = None,
        true_label="Yes",
        false_label="No",
        default: bool = True,
        required: bool = True,
    ) -> None:
        true_select = SelectOption(label=true_label, value="True", default=default)
        false_select = SelectOption(
            label=false_label, value="False", default=not default
        )

        self.input = ui.Select(
            custom_id=custom_id or MISSING,
            options=[true_select, false_select],
            required=required,
        )
        super().__init__(text=label, component=self.input)

    def validate(self):
        if len(self.input.values) != 1:
            raise ValueError(f"Make exactly one selection, not {self.input.values}")
        [raw] = self.input.values
        if raw == "True":
            return True
        if raw == "False":
            return False
        raise ValueError(f"{raw} was not True or False!")


# TODO: select fields if needed
