"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   DARK POOL NEGOTIATOR — Dynamic Price Discovery                ║
║   x402 Clearinghouse Haggling Protocol                          ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                    ║
║   Creates: Autonomous price discovery via micro-negotiations    ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

This turns x402 from a fixed-price store into a live market.
Agents discover the real price through thousands of micro-negotiations.
"""

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

class NegotiationStatus(Enum):
    ACCEPTED = "ACCEPTED"
    COUNTERED = "COUNTERED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class NegotiationResult:
    status: NegotiationStatus
    final_price: float
    message: str = ""
    session_id: Optional[str] = None
    expires_at: Optional[int] = None


class PriceNegotiator:
    """
    Server-side pricing engine.
    Decides whether to accept, counter, or reject bids based on:
    - Inventory levels (desperation)
    - Time of day (urgency)
    - Agent reputation (trust)
    - Market conditions (external signals)
    """

    def __init__(
        self,
        base_price: float,
        min_price: float,
        max_discount: float = 0.10,  # Max 10% discount
        inventory: int = 1000
    ):
        self.base_price = base_price
        self.min_price = min_price
        self.max_discount = max_discount
        self.inventory = inventory

        # Track negotiation sessions
        self.sessions: Dict[str, Dict] = {}

        # Stats
        self.total_negotiations = 0
        self.accepted_count = 0
        self.countered_count = 0
        self.rejected_count = 0

    def _calculate_flexibility(self) -> float:
        """
        The 'Desperation Algorithm'
        High inventory = more flexible on price
        Low inventory = firm pricing
        """
        if self.inventory > 800:
            return 0.05  # 5% flexible
        elif self.inventory > 500:
            return 0.03  # 3% flexible
        elif self.inventory > 200:
            return 0.01  # 1% flexible
        else:
            return 0.0   # No flexibility, inventory is scarce

    def _calculate_reputation_bonus(self, agent_address: str) -> float:
        """
        Trusted agents get better prices.
        In production, query AgentRegistry for reputation score.
        """
        # TODO: Query AgentRegistry contract
        # For now, return 0 (no bonus)
        return 0.0

    def evaluate_bid(
        self,
        bid_amount: float,
        agent_address: str,
        volume: int = 1,
        urgency: str = "normal"
    ) -> NegotiationResult:
        """
        Core decision engine.
        Evaluates a bid and returns: ACCEPT, COUNTER, or REJECT
        """
        self.total_negotiations += 1

        # Calculate our flexibility
        flexibility = self._calculate_flexibility()
        reputation_bonus = self._calculate_reputation_bonus(agent_address)

        # Volume discount (buy more, pay less per unit)
        volume_discount = min(0.02, volume * 0.001)  # Up to 2% for large orders

        # Total discount available
        total_discount = min(self.max_discount, flexibility + reputation_bonus + volume_discount)

        # Our floor price for this negotiation
        floor_price = self.base_price * (1 - total_discount)

        # Ensure we never go below absolute minimum
        floor_price = max(floor_price, self.min_price)

        # === DECISION LOGIC ===

        # ACCEPT: Bid meets or exceeds our floor
        if bid_amount >= floor_price:
            self.accepted_count += 1
            self.inventory -= volume
            return NegotiationResult(
                status=NegotiationStatus.ACCEPTED,
                final_price=bid_amount,
                message="Deal accepted.",
                expires_at=int(time.time()) + 300  # 5 min to settle
            )

        # COUNTER: Bid is below floor but above absolute minimum
        elif bid_amount >= self.min_price:
            self.countered_count += 1
            # Meet in the middle
            counter_price = round((floor_price + bid_amount) / 2, 2)
            counter_price = max(counter_price, self.min_price)

            return NegotiationResult(
                status=NegotiationStatus.COUNTERED,
                final_price=counter_price,
                message=f"Too low. Counter-offer: ${counter_price:.2f}",
                expires_at=int(time.time()) + 60  # 1 min to respond
            )

        # REJECT: Bid is insulting
        else:
            self.rejected_count += 1
            return NegotiationResult(
                status=NegotiationStatus.REJECTED,
                final_price=self.base_price,
                message=f"Price is firm at ${self.base_price:.2f}. Your bid was too low."
            )

    def get_stats(self) -> Dict[str, Any]:
        """Returns negotiation statistics"""
        return {
            "total_negotiations": self.total_negotiations,
            "accepted": self.accepted_count,
            "countered": self.countered_count,
            "rejected": self.rejected_count,
            "acceptance_rate": self.accepted_count / max(1, self.total_negotiations),
            "current_inventory": self.inventory,
            "base_price": self.base_price,
            "min_price": self.min_price
        }


class AgentHaggler:
    """
    Client-side negotiation engine.
    Teaches agents to fight for better prices.
    """

    def __init__(self, max_rounds: int = 3, aggression: float = 0.1):
        """
        aggression: How much to lowball (0.1 = start 10% below max budget)
        max_rounds: Max negotiation attempts before walking away
        """
        self.max_rounds = max_rounds
        self.aggression = aggression
        self.negotiation_history = []

    def calculate_opening_bid(self, max_budget: float) -> float:
        """Start aggressive, leave room to negotiate up"""
        return max_budget * (1 - self.aggression)

    def calculate_counter_bid(
        self,
        their_price: float,
        my_last_bid: float,
        max_budget: float,
        round_num: int
    ) -> Optional[float]:
        """
        Decide how to respond to a counter-offer.
        As rounds increase, we get less aggressive.
        """
        # If their price is in budget, just accept
        if their_price <= max_budget:
            return their_price

        # Calculate how much room we have
        room = max_budget - my_last_bid

        # Each round, we give up more of our room
        concession = room * (round_num / self.max_rounds)

        new_bid = my_last_bid + concession

        # Never bid more than our max
        return min(new_bid, max_budget)

    def should_walk_away(
        self,
        their_price: float,
        max_budget: float,
        round_num: int
    ) -> bool:
        """Decide if we should abandon this negotiation"""
        # If we've exceeded max rounds, walk away
        if round_num >= self.max_rounds:
            return True

        # If their price is way above budget (>20%), walk away
        if their_price > max_budget * 1.2:
            return True

        return False


# === FASTAPI SERVER INTEGRATION ===

def create_negotiation_routes(app, negotiator: PriceNegotiator):
    """
    Add negotiation endpoints to an existing FastAPI app.

    Usage:
        from fastapi import FastAPI
        from negotiator import PriceNegotiator, create_negotiation_routes

        app = FastAPI()
        negotiator = PriceNegotiator(base_price=100, min_price=90)
        create_negotiation_routes(app, negotiator)
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.post("/api/v1/trade/negotiate")
    async def negotiate_price(request: Request):
        data = await request.json()

        bid = float(data.get("bid", 0))
        asset_id = data.get("asset_id", "UNKNOWN")
        agent_address = data.get("agent_address", "0x0")
        volume = int(data.get("volume", 1))

        result = negotiator.evaluate_bid(
            bid_amount=bid,
            agent_address=agent_address,
            volume=volume
        )

        headers = {
            "X-402-Price": str(result.final_price),
            "X-402-Status": result.status.value,
            "X-402-Message": result.message,
        }

        if result.expires_at:
            headers["X-402-Expires"] = str(result.expires_at)

        # Always return 402 - the price header tells them the deal
        return JSONResponse(
            content={
                "status": result.status.value,
                "price": result.final_price,
                "message": result.message
            },
            status_code=402,
            headers=headers
        )

    @app.get("/api/v1/trade/negotiate/stats")
    async def negotiation_stats():
        return negotiator.get_stats()

    return app


# === STANDALONE TEST ===

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   DARK POOL NEGOTIATOR — Test Run                           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # Create negotiator (server side)
    negotiator = PriceNegotiator(
        base_price=100.00,
        min_price=90.00,
        inventory=1000
    )

    # Create haggler (agent side)
    haggler = AgentHaggler(max_rounds=3, aggression=0.15)

    # Simulate negotiation
    max_budget = 97.00
    agent = "0xAgent123"

    print(f"[AGENT] Max budget: ${max_budget}")
    print(f"[SERVER] Base price: ${negotiator.base_price}")
    print(f"[SERVER] Min price: ${negotiator.min_price}")
    print()

    # Round 1: Opening bid
    my_bid = haggler.calculate_opening_bid(max_budget)
    print(f"[ROUND 1] Agent bids: ${my_bid:.2f}")

    result = negotiator.evaluate_bid(my_bid, agent)
    print(f"[ROUND 1] Server: {result.status.value} @ ${result.final_price:.2f}")
    print(f"          {result.message}")
    print()

    if result.status == NegotiationStatus.ACCEPTED:
        print(f"[DEAL] Closed at ${result.final_price:.2f}")
    elif result.status == NegotiationStatus.COUNTERED:
        # Round 2: Counter
        my_bid = haggler.calculate_counter_bid(
            result.final_price, my_bid, max_budget, 2
        )
        print(f"[ROUND 2] Agent counters: ${my_bid:.2f}")

        result = negotiator.evaluate_bid(my_bid, agent)
        print(f"[ROUND 2] Server: {result.status.value} @ ${result.final_price:.2f}")

        if result.status == NegotiationStatus.ACCEPTED:
            print(f"\n[DEAL] Closed at ${result.final_price:.2f}")
        elif result.final_price <= max_budget:
            print(f"\n[DEAL] Accepting counter @ ${result.final_price:.2f}")
        else:
            print(f"\n[WALK] Price ${result.final_price:.2f} > budget ${max_budget}")

    print()
    print("Stats:", negotiator.get_stats())
