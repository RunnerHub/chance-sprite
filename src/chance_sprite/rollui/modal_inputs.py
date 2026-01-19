from discord import ui


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
        value = int(raw)
        if value < self.min_value or value > self.max_value:
            raise ValueError(
                f"Pick a number between {self.min_value} and {self.max_value}."
            )
        return value


# TODO: select fields if needed
