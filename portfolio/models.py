from django.db import models

from trading.models import Stock, TradingSignal


class Portfolio(models.Model):
    class Broker(models.TextChoices):
        ALPACA = "ALPACA", "Alpaca"
        SNAPTRADE = "SNAPTRADE", "SnapTrade"

    name = models.CharField(max_length=100, unique=True)
    broker = models.CharField(max_length=20, choices=Broker.choices, default=Broker.ALPACA)
    account_id = models.CharField(max_length=100, blank=True)
    is_paper = models.BooleanField(default=True)
    initial_capital = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cash = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def market_value(self):
        return sum((p.market_value for p in self.positions.all()), 0)

    @property
    def total_value(self):
        return self.cash + self.market_value


class Position(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="positions")
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT, related_name="positions")
    quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    average_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    current_price = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stock__symbol"]
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "stock"], name="unique_position_per_portfolio_stock"),
        ]

    def __str__(self):
        return f"{self.portfolio.name}: {self.quantity} {self.stock.symbol}"

    @property
    def market_value(self):
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self):
        return (self.current_price - self.average_cost) * self.quantity


class Order(models.Model):
    class Side(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUBMITTED = "SUBMITTED", "Submitted"
        FILLED = "FILLED", "Filled"
        PARTIALLY_FILLED = "PARTIAL", "Partially filled"
        CANCELLED = "CANCELLED", "Cancelled"
        REJECTED = "REJECTED", "Rejected"

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="orders")
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT, related_name="orders")
    signal = models.ForeignKey(
        TradingSignal, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    filled_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    filled_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    broker_order_id = models.CharField(max_length=100, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    filled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.side} {self.quantity} {self.stock.symbol} [{self.status}]"


class PortfolioSnapshot(models.Model):
    """Daily record of portfolio value, used for performance charts."""

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="snapshots")
    date = models.DateField()
    cash = models.DecimalField(max_digits=14, decimal_places=2)
    market_value = models.DecimalField(max_digits=14, decimal_places=2)
    total_value = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "date"], name="unique_snapshot_per_portfolio_date"),
        ]

    def __str__(self):
        return f"{self.portfolio.name} {self.date} total={self.total_value}"
