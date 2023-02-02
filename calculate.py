from collections import deque
from csv import DictReader
from datetime import datetime
from decimal import Decimal, getcontext
# from pickle import dump
# from pprint import pprint
from sys import argv
from typing import Dict, Deque


ticker_to_traits = {
    "BTCE": {
        "type": "etf",
        "teilfreistellung": Decimal(1),
    },
    "EQQQ": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "EUNL": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "GE": {
        "type": "stock",
    },
    "IS3N": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "INRG": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "IUSN": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "PHGP": {
        "type": "etf",
        "teilfreistellung": Decimal(1),
    },
    "SGLN": {
        "type": "etf",
        "teilfreistellung": Decimal(1),
    },
    "VUAA": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "VUSA": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "VWRA": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
    "VWRL": {
        "type": "etf",
        "teilfreistellung": Decimal(0.7),
    },
}

"""
Yearly constants
"""
basiszins = {
    "2020": Decimal(0.88),
    "2021": Decimal(-0.45)
}
freibetrag = Decimal(801)
pauschalsteuer = Decimal(0.25)
solidaritätszuschlag = Decimal(1.055)


class Transaction:

    def __init__(self, row):
        self.ticker: str = row["Ticker"]
        self.time: datetime = datetime.strptime(row["Time"], "%Y-%m-%d %H:%M:%S")
        self.exchange_rate: Decimal = Decimal(row["Exchange rate"]) if row["Exchange rate"] else Decimal(0)
        self.price_per_share: Decimal = Decimal(row["Price / share"]) if row["Price / share"] else Decimal(0)
        self.num_of_shares: Decimal = Decimal(row["No. of shares"]) if row["No. of shares"] else Decimal(0)
        self.currency = row["Currency (Price / share)"]
        self.teilfreistellung: Decimal = ticker_to_traits[self.ticker]["teilfreistellung"] if ticker_to_traits[self.ticker]["type"] == "etf" else Decimal(1)


def calculate_pnl(f: "Transaction", t: "Transaction") -> Decimal:
    if f.currency == "GBX":
        cf = Decimal(1) / f.exchange_rate / 100 * f.price_per_share / 100
        ct = Decimal(1) / t.exchange_rate / 100 * t.price_per_share / 100
    else:
        cf = Decimal(1) / f.exchange_rate * f.price_per_share
        ct = Decimal(1) / t.exchange_rate * t.price_per_share
    f.num_of_shares -= t.num_of_shares
    pnl = t.num_of_shares * (cf - ct)
    return pnl


def calculate_current_total_value_foreach_ticker(ticker_to_deque: Dict[str, Deque["Transaction"]]) -> Dict[str, Decimal]:
    ticker_to_total_val = dict()
    for t, d in ticker_to_deque.items():
        total = Decimal(0)
        for tx in d:
            if tx.currency == "GBX":
                total += Decimal(1) / tx.exchange_rate / 100 * tx.price_per_share / 100
            else:
                total += Decimal(1) / tx.exchange_rate * tx.price_per_share
        ticker_to_total_val[t] = total
    return ticker_to_total_val


def main():
    """
    Set decimal precision
    """
    getcontext().prec = 8

    """
    Get the year of tax return from argument
    """
    fname = argv[1]
    year = fname.split(".")[0]

    """
    TODO: Reconstruct deque for each ticker from file
    """
    ticker_to_deque = dict()

    """
    TODO: Reconstruct Vorabpauschalen paid per share for each ticker from file
    """
    ticker_to_yearly_vorabpauschalen = dict()

    """
    Calculate ETF values for the start of the year (used for Vorabpauschale)
    """
    ticker_to_total_val_soy = calculate_current_total_value_foreach_ticker(ticker_to_deque)

    """
    Calculate this year's tax
    """
    ticker_to_total_pnl = dict()
    ticker_to_total_vorabpauschalen_return = dict()
    with open(fname, newline="") as tax:
        reader = DictReader(tax, delimiter=",")
        for row in reader:
            dq = ticker_to_deque.get(ticker, deque())

            if row["Action"] == "Market buy":
                tx = Transaction(row)
                dq.append(tx)
            elif row["Action"] == "Market sell":
                tx = Transaction(row)
                dq = get_transaction_deque_by_ticker(ticker_to_deque, tx.ticker)

                """
                Keep deque / calculating until the selling share is smaller than the front of the queue's shares
                """
                while dq and tx.num_of_shares >= dq[0].num_of_shares:
                    curr = dq.popleft()

                    ticker_to_total_pnl[tx.ticker] += calculate_pnl(tx, curr)

                    for ticker, yearly_vorabpauschalen_per_share in ticker_to_yearly_vorabpauschalen_per_share:


                    vorabpauschale_return = tx.num_of_shares * ticker_to_yearly_vorabpauschalen_per_share[tx.ticker]
                    ticker_to_total_vorabpauschalen_return[tx.ticker] = ticker_to_total_vorabpauschalen_return.get(tx.ticker, 0) + vorabpauschalen_return

                """
                Calculate the remaining shares
                """
                if dq and tx.num_of_shares > 0.0:
                    ticker_to_total_pnl[tx.ticker] += calculate_pnl(dq[0], tx)
                    vorabpauschale_return = tx.num_of_shares * ticker_to_yearly_vorabpauschalen_per_share[tx.ticker]
                    ticker_to_total_vorabpauschalen_return[tx.ticker] = ticker_to_total_vorabpauschalen_return.get(tx.ticker, 0) + vorabpauschalen_return

            elif row["Action"] == "Dividend (Ordinary)":
                pass
            elif row["Action"] == "Deposit":
                pass

            ticker_to_deque[ticker] = dq

    """
    Calculate ETF values for the end of the year (used for Vorabpauschale) based on what's left in queue, with monthly ratio
    """
    ticker_to_total_val_eoy = calculate_current_total_value_foreach_ticker(ticker_to_deque)

    """
    Zip soy / eoy value for each ticker
    """
    ticker_to_soy_eoy = dict()
    for ticker, total_val_eoy in ticker_to_total_val_eoy.items():
        if ticker not in ticker_to_total_val_soy:
            ticker_to_soy_eoy[ticker] = (Decimal(0), total_val_eoy)
        else:
            ticker_to_soy_eoy[ticker] = (ticker_to_total_val_soy[ticker], total_val_eoy)

    """
    Calculate this year's Vorabpauschalen
    """
    for ticker, soy_eoy in ticker_to_soy_eoy.items():
        dq = ticker_to_deque[ticker]
        vorabpauschalen = Decimal(0)
        shares = Decimal(0)
        for tx in dq:
            basisertrag = min(soy_eoy[0] * basiszins[year] * Decimal(0.7), soy_eoy[1] - soy_eoy[0]) * Decimal(((tx.time.month - 1) / 12)) - dividend
            basisertrag = Decimal(0) if basisertrag < 0 else basisertrag  # negative Basisertrag does not exist
            vorabpauschalen += basisertrag
            shares += tx.num_of_shares
        ticker_to_yearly_vorabpauschalen_per_share[ticker] = vorabpauschalen / shares

    """
    Calculate total tax & total Vorabpauschalen return
    """
    ticker_to_tax = dict()
    ticker_to_vorabpauschalen_return = dict()
    for ticker, pnl in ticker_to_total_pnl.items():
        total_pnl += taxable_event.pnl * taxable_event.teilfreistellung if taxable_event.pnl > 0 else taxable_event.pnl
        total_vorabpauschalen_return += sum(taxable_event.vorabpauschalen_return)
        # TODO: Calculate Quellensteuer
        ticker_to_tax[ticker] = ((ticker[] + total_vorabpauschalen_this_year - freibetrag) * pauschalsteuer - total_quellensteuer) * solidaritätszuschlag - total_vorabpauschalen_return

    print("Total Vorabpauschalen This Year: " + str(total_vorabpauschalen_this_year))
    print("Total Vorabpauschalen Return   : " + str(total_vorabpauschalen_return))
    print("Total Tax                      : " + str(total_tax))

    """
    TODO: Write to file Vorabpauschalen per share
    """

    """
    TODO: Write to file the current deque state for each ticker, write the total deposit as well
    """


if __name__ == "__main__":
    main()
