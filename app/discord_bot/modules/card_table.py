from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Sequence

from PIL import Image, ImageDraw

from app.discord_bot.modules.card import Card
from app.discord_bot.modules.helpers import ABS_PATH


def hand_to_images(hand: Sequence[Card]) -> list[Image.Image]:
    images: list[Image.Image] = []
    for card in hand:
        with Image.open(ABS_PATH / "modules" / "cards" / card.image) as img:
            images.append(img.convert("RGBA"))
    return images


def compose_card_table(
    dealer_hand: list[Image.Image],
    player_hands: list[list[Image.Image]],
    *,
    active_hand_index: int | None = None,
) -> Image.Image:
    """Creates table layout with dealer top-center and player hands below."""
    if not dealer_hand or not player_hands:
        raise ValueError("at least one non-empty hand is required")
    if any(not hand for hand in player_hands):
        raise ValueError("all player hands must be non-empty")

    bg = Image.open(ABS_PATH / "modules" / "table.png").convert("RGBA")
    bg_w, bg_h = bg.size

    base_w, base_h = dealer_hand[0].size
    col_gap = 10
    padding = 16
    divider_clearance = 24
    lane_gap = divider_clearance * 2
    dealer_to_player_gap = 24
    player_row_gap = 18
    active_border = 7

    has_split_layout = len(player_hands) > 1
    available_w = max(1, bg_w - (padding * 2))
    lane_count = 2 if has_split_layout else 1
    lane_width = (available_w - lane_gap) // 2 if lane_count == 2 else available_w

    player_lanes: list[list[int]]
    if lane_count == 1:
        player_lanes = [list(range(len(player_hands)))]
    else:
        player_lanes = [
            [i for i in range(len(player_hands)) if i % 2 == 0],
            [i for i in range(len(player_hands)) if i % 2 == 1],
        ]

    max_cards_dealer = len(dealer_hand)
    max_cards_player = max(len(hand) for hand in player_hands)
    rows_per_lane = max(len(lane) for lane in player_lanes)

    dealer_width_limit = (available_w - ((max_cards_dealer - 1) * col_gap)) / max_cards_dealer
    player_width_limit = (lane_width - ((max_cards_player - 1) * col_gap)) / max_cards_player

    available_h = max(1, bg_h - (padding * 2))
    vertical_card_limit = (
        available_h
        - dealer_to_player_gap
        - ((rows_per_lane - 1) * player_row_gap)
    ) / (rows_per_lane + 1)

    scale = min(
        1.0,
        dealer_width_limit / base_w,
        player_width_limit / base_w,
        vertical_card_limit / base_h,
    )
    if scale <= 0:
        scale = 0.2

    card_w = max(1, int(base_w * scale))
    card_h = max(1, int(base_h * scale))

    resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
    resized_images: list[Image.Image] = []
    rendered_dealer: list[Image.Image] = []
    for card in dealer_hand:
        if card.size == (card_w, card_h):
            rendered_dealer.append(card)
        else:
            resized = card.resize((card_w, card_h), resample)
            rendered_dealer.append(resized)
            resized_images.append(resized)

    rendered_players: list[list[Image.Image]] = []
    for hand in player_hands:
        rendered_hand: list[Image.Image] = []
        for card in hand:
            if card.size == (card_w, card_h):
                rendered_hand.append(card)
            else:
                resized = card.resize((card_w, card_h), resample)
                rendered_hand.append(resized)
                resized_images.append(resized)
        rendered_players.append(rendered_hand)

    total_h = (
        card_h
        + dealer_to_player_gap
        + (rows_per_lane * card_h)
        + ((rows_per_lane - 1) * player_row_gap)
    )
    start_y = max(padding, (bg_h - total_h) // 2)
    draw = ImageDraw.Draw(bg)

    try:
        dealer_row_w = (len(rendered_dealer) * card_w) + ((len(rendered_dealer) - 1) * col_gap)
        dealer_x = max(padding, (bg_w - dealer_row_w) // 2)
        for card in rendered_dealer:
            bg.alpha_composite(card, (dealer_x, start_y))
            dealer_x += card_w + col_gap

        player_start_y = start_y + card_h + dealer_to_player_gap

        if lane_count == 2:
            divider_x = bg_w // 2
            divider_top = max(padding, player_start_y - 6)
            divider_bottom = min(
                bg_h - padding,
                player_start_y + (rows_per_lane * card_h) + ((rows_per_lane - 1) * player_row_gap) + 6,
            )
            draw.line(
                ((divider_x, divider_top), (divider_x, divider_bottom)),
                fill=(255, 255, 255, 170),
                width=3,
            )

        for lane_i, lane in enumerate(player_lanes):
            for row_i, hand_index in enumerate(lane):
                hand = rendered_players[hand_index]
                row_w = (len(hand) * card_w) + ((len(hand) - 1) * col_gap)
                row_y = player_start_y + (row_i * (card_h + player_row_gap))

                if lane_count == 2:
                    if lane_i == 0:
                        row_x = divider_x - divider_clearance - row_w
                    else:
                        row_x = divider_x + divider_clearance
                else:
                    row_x = padding + max(0, (lane_width - row_w) // 2)

                if active_hand_index is not None and hand_index == active_hand_index:
                    border_box = (
                        row_x - active_border,
                        row_y - active_border,
                        row_x + row_w + active_border,
                        row_y + card_h + active_border,
                    )
                    draw.rectangle(
                        border_box,
                        outline=(255, 215, 0, 255),
                        width=6,
                        fill=(255, 215, 0, 45),
                    )
                    label_text = "ACTIVE"
                    if hasattr(draw, "textbbox"):
                        text_bbox = draw.textbbox((0, 0), label_text)
                        text_w = text_bbox[2] - text_bbox[0]
                        text_h = text_bbox[3] - text_bbox[1]
                    else:
                        text_w, text_h = draw.textsize(label_text)
                    text_x = row_x + max(0, (row_w - text_w) // 2)
                    text_y = max(padding, row_y - text_h - active_border - 8)
                    draw.rectangle(
                        (text_x - 8, text_y - 4, text_x + text_w + 8, text_y + text_h + 4),
                        fill=(255, 215, 0, 230),
                    )
                    draw.text((text_x, text_y), label_text, fill=(40, 40, 40, 255))

                for card in hand:
                    bg.alpha_composite(card, (row_x, row_y))
                    row_x += card_w + col_gap

        return bg
    finally:
        for image in resized_images:
            image.close()


def render_card_table(
    output: Path | str | BinaryIO,
    dealer_hand: Sequence[Card],
    player_hands: Sequence[Sequence[Card]],
    *,
    active_hand_index: int | None = None,
    image_format: str | None = None,
) -> None:
    """Renders a card table to a filesystem path or writable binary stream."""
    dealer_images = hand_to_images(dealer_hand)
    player_images = [hand_to_images(hand) for hand in player_hands]
    final_image: Image.Image | None = None
    try:
        final_image = compose_card_table(
            dealer_images,
            player_images,
            active_hand_index=active_hand_index,
        )
        if isinstance(output, (str, Path)):
            final_image.save(output)
        else:
            final_image.save(output, format=image_format or "PNG")
            if hasattr(output, "seek"):
                output.seek(0)
    finally:
        if final_image:
            final_image.close()
        for image in dealer_images:
            image.close()
        for hand in player_images:
            for image in hand:
                image.close()


def render_card_table_bytes(
    dealer_hand: Sequence[Card],
    player_hands: Sequence[Sequence[Card]],
    *,
    active_hand_index: int | None = None,
) -> BytesIO:
    """Renders a card table and returns an in-memory PNG buffer."""
    output = BytesIO()
    render_card_table(
        output,
        dealer_hand,
        player_hands,
        active_hand_index=active_hand_index,
        image_format="PNG",
    )
    output.seek(0)
    return output
