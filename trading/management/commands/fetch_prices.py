from django.core.management.base import BaseCommand, CommandError

from trading.models import Stock
from trading.services.massive_client import MassiveClient, MassiveError, update_prices


class Command(BaseCommand):
    help = "Fetch missing daily prices from Massive and store them in PriceData."

    def add_arguments(self, parser):
        parser.add_argument(
            "symbols",
            nargs="*",
            help="Tickers to fetch (e.g. AAPL MSFT). New ones are added as Stocks. Default: all active stocks.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=400,
            help="How far back to go for stocks with no price history yet (default: 400).",
        )

    def handle(self, *args, **options):
        try:
            client = MassiveClient()
        except MassiveError as exc:
            raise CommandError(str(exc))

        symbols = [s.upper() for s in options["symbols"]]
        if symbols:
            for symbol in symbols:
                _, created = Stock.objects.get_or_create(symbol=symbol)
                if created:
                    self.stdout.write(f"Added new stock {symbol}")
            stocks = Stock.objects.filter(symbol__in=symbols)
        else:
            stocks = Stock.objects.filter(is_active=True)

        if not stocks.exists():
            raise CommandError("No stocks to fetch. Pass tickers, e.g. `python manage.py fetch_prices AAPL MSFT`.")

        self.stdout.write(f"Fetching prices for {stocks.count()} stock(s)... (free plan: ~12s per stock)")
        result = update_prices(stocks=stocks, lookback_days=options["days"], client=client)

        self.stdout.write(self.style.SUCCESS(f"Saved {result['saved']} new price rows."))
        if result["failed"]:
            self.stdout.write(self.style.WARNING(f"Failed: {', '.join(result['failed'])} (see log for details)"))
