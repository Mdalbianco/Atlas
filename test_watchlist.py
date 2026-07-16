from app.services.watchlist_service import WatchlistService


def main() -> None:
    watchlist = WatchlistService()

    print("Watchlist iniziale:")
    print(watchlist.get_symbols())

    added = watchlist.add_symbol("LINK")
    print(f"LINK aggiunto: {added}")

    print("Watchlist aggiornata:")
    print(watchlist.get_symbols())

    removed = watchlist.remove_symbol("LINK")
    print(f"LINK rimosso: {removed}")

    print("Watchlist finale:")
    print(watchlist.get_symbols())


if __name__ == "__main__":
    main()