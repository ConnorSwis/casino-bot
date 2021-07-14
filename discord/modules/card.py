import os


class Card:
    suits = ["clubs", "diamonds", "hearts", "spades"]
    def __init__(self, suit: str, value: int, down=False):
        self.suit = suit
        self.value = value
        self.down = down
        self.symbol = self.name[0].upper()

    @property
    def name(self) -> str:
        """The name of the card value."""
        if self.value <= 10: return str(self.value)
        else: return {
            11: 'jack',
            12: 'queen',
            13: 'king',
            14: 'ace',
        }[self.value]

    @property
    def image(self):
        return (
            f"{self.symbol if self.name != '10' else '10'}"\
            f"{self.suit[0].upper()}.png" \
            if not self.down else "red_back.png"
        )

    def flip(self):
        self.down = not self.down
        return self

    def __str__(self) -> str:
        return f'{self.name.title()} of {self.suit.title()}'

    def __repr__(self) -> str:
        return str(self)