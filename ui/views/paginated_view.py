import discord


class PaginationView(discord.ui.View):
    def __init__(
        self,
        pages: list[discord.Embed],
        *,
        author_id: int | None = None,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)

        if not pages:
            raise ValueError("PaginationView requires at least one page")

        self.pages = pages
        self.current_page = 0
        self.author_id = author_id
        self.message: discord.Message | None = None

        self._update_buttons()

    def _update_buttons(self) -> None:
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1

        self.page_button.label = (
            f"{self.current_page + 1}/{len(self.pages)}"
        )

    async def _show_page(
        self,
        interaction: discord.Interaction,
    ) -> None:
        self._update_buttons()

        await interaction.response.edit_message(
            embed=self.pages[self.current_page],
            view=self,
        )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if self.author_id is None or interaction.user.id == self.author_id:
            return True

        await interaction.response.send_message(
            "Only the person who opened this list can use these buttons.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current_page -= 1
        await self._show_page(interaction)

    @discord.ui.button(
        label="1/1",
        style=discord.ButtonStyle.secondary,
        disabled=True,
    )
    async def page_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        pass

    @discord.ui.button(
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.current_page += 1
        await self._show_page(interaction)