from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255, blank=True)
    exchange = models.CharField(max_length=50, blank=True)
    sector = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self):
        return self.symbol


class PriceData(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="prices")
    date = models.DateField()
    open = models.DecimalField(max_digits=12, decimal_places=4)
    high = models.DecimalField(max_digits=12, decimal_places=4)
    low = models.DecimalField(max_digits=12, decimal_places=4)
    close = models.DecimalField(max_digits=12, decimal_places=4)
    volume = models.BigIntegerField()

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["stock", "date"], name="unique_price_per_stock_date"),
        ]
        indexes = [models.Index(fields=["stock", "date"])]

    def __str__(self):
        return f"{self.stock.symbol} {self.date} close={self.close}"


class MomentumScore(models.Model):
    """12-1 momentum: return over the last 12 months, skipping the most recent month."""

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="momentum_scores")
    date = models.DateField()
    lookback_months = models.PositiveSmallIntegerField(default=12)
    skip_months = models.PositiveSmallIntegerField(default=1)
    score = models.DecimalField(max_digits=10, decimal_places=6)
    rank = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "rank"]
        constraints = [
            models.UniqueConstraint(fields=["stock", "date"], name="unique_momentum_per_stock_date"),
        ]

    def __str__(self):
        return f"{self.stock.symbol} {self.date} score={self.score} rank={self.rank}"


class TradingSignal(models.Model):
    class SignalType(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"
        HOLD = "HOLD", "Hold"

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="signals")
    momentum_score = models.ForeignKey(
        MomentumScore, on_delete=models.SET_NULL, null=True, blank=True, related_name="signals"
    )
    rebalance_event = models.ForeignKey(
        "RebalanceEvent", on_delete=models.CASCADE, null=True, blank=True, related_name="signals"
    )
    signal_type = models.CharField(max_length=4, choices=SignalType.choices)
    target_weight = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    executed = models.BooleanField(default=False)
    executed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.signal_type} {self.stock.symbol} ({self.created_at:%Y-%m-%d})"


class RebalanceEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    top_n = models.PositiveIntegerField(default=10)
    num_buys = models.PositiveIntegerField(default=0)
    num_sells = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Rebalance {self.date} [{self.status}]"
