# The mathematics behind Poker Decision Lab

This document collects every formula the engine uses, with short derivations, and
points to the code that implements each one. Notation: the **hero** is the player
facing the decision; the **opponent** has just bet.

---

## 1. Counting cards and hands

A card is an integer $c \in \{0,\dots,51\}$ with rank $r = \lfloor c/4 \rfloor$
(0 = deuce … 12 = ace) and suit $s = c \bmod 4$ ([`cards.py`](../src/pokerlab/cards.py)).

| Quantity | Value |
|---|---|
| Two-card starting hands (combos) | $\binom{52}{2} = 1{,}326$ |
| Strategically distinct starting hands (classes) | $169$: 13 pairs × 6 combos, 78 suited × 4, 78 offsuit × 12 |
| Five-card hands | $\binom{52}{5} = 2{,}598{,}960$ |
| Distinct five-card hand strengths | $7{,}462$ |

Pairs have $\binom{4}{2} = 6$ suit combinations, suited hands 4 (one per suit),
offsuit hands $4 \times 3 = 12$; indeed $13 \cdot 6 + 78 \cdot 4 + 78 \cdot 12 = 1{,}326$.

The category counts of all five-card hands, which the tests check exhaustively, are:

| Category | Count | Derivation |
|---|---:|---|
| Straight flush | 40 | 10 straights × 4 suits |
| Four of a kind | 624 | $13 \cdot 48$ |
| Full house | 3,744 | $13 \binom{4}{3} \cdot 12 \binom{4}{2}$ |
| Flush | 5,108 | $4\binom{13}{5} - 40$ |
| Straight | 10,200 | $10 \cdot 4^5 - 40$ |
| Three of a kind | 54,912 | $13\binom{4}{3}\binom{12}{2}4^2$ |
| Two pair | 123,552 | $\binom{13}{2}\binom{4}{2}^2 \cdot 44$ |
| One pair | 1,098,240 | $13\binom{4}{2}\binom{12}{3}4^3$ |
| High card | 1,302,540 | $(\binom{13}{5} - 10)(4^5 - 4)$ |

## 2. Hand evaluation

The evaluator ([`evaluator.py`](../src/pokerlab/evaluator.py)) maps 5–7 cards to an
integer score such that **comparing scores is comparing poker hands**:

$$
\text{score} = (\text{category} \ll 20) \;|\; (t_1 \ll 16) \;|\; (t_2 \ll 12) \;|\; (t_3 \ll 8) \;|\; (t_4 \ll 4) \;|\; t_5
$$

where the category is 0 (high card) … 8 (straight flush) and $t_1,\dots,t_5$ are the
tie-break ranks in order of importance (e.g. two pair: high pair, low pair, kicker).
Each field has 4 bits, so integer order equals lexicographic order of
(category, $t_1, \dots, t_5$). For 6 or 7 cards the score is the maximum over all
5-card subsets; the evaluator computes it directly from rank and suit counts, and a
test checks it against the brute-force maximum.

The vectorised version ([`evaluator_fast.py`](../src/pokerlab/evaluator_fast.py))
computes the same score for an $N \times k$ array of hands using per-hand rank counts,
13-bit rank masks and two 8,192-entry lookup tables (highest straight in a mask; top
five ranks of a mask, already packed in tie-break order).

## 3. Ranges, weights and card removal

A range assigns a weight $w_h \in [0,1]$ to each hand class $h$
([`ranges.py`](../src/pokerlab/ranges.py)): the probability that the opponent holds
(and bets) a combo of that class, relative to a hand they always bet. Each combo
$k$ inherits its class weight $w_k$.

Given the visible cards $D$ (hero's cards and the board), combos that use a card in
$D$ are impossible. The opponent's combo distribution is

$$
P(\text{combo} = k \mid D) = \frac{w_k \,\mathbb{1}[k \cap D = \emptyset]}{\sum_j w_j \,\mathbb{1}[j \cap D = \emptyset]}.
$$

This is Bayes' rule with a uniform deal: every combo that avoids $D$ was equally
likely to be dealt, so conditioning on $D$ only removes the impossible ones.

## 4. Equity

**Equity** is the hero's expected share of the pot at showdown, with no further betting:

$$
E = P(\text{win}) + \tfrac{1}{2} P(\text{tie}).
$$

### Exact enumeration

Let $k$ be the number of board cards still to come. For a fixed opponent combo, every
$k$-subset $R$ of the remaining $n = 52 - |D| - 2$ cards is equally likely, and there
are $\binom{n}{k}$ of them (990 on the flop, 44 on the turn, 1 on the river). Writing
$e_k$ for the hero's equity against combo $k$ averaged over its runouts,

$$
E = \sum_k P(k \mid D)\, e_k, \qquad
e_k = \frac{1}{\binom{n}{k}} \sum_R \Big(\mathbb{1}[\text{hero wins}] + \tfrac{1}{2}\mathbb{1}[\text{tie}]\Big).
$$

Because $\binom{n}{k}$ is the same for every combo, this equals the weighted average over
all (combo, runout) pairs, which is how [`equity.py`](../src/pokerlab/equity.py)
computes it in one vectorised batch.

### Monte Carlo

Each trial draws a combo $k \sim P(k \mid D)$, then a uniform runout from the cards
left, and records a score $X \in \{0, \tfrac{1}{2}, 1\}$. This two-stage draw samples
exactly the joint distribution above, so $\bar{X}$ is an unbiased estimator of $E$.
(The runout is drawn by giving every remaining card an independent uniform key,
pushing the opponent's two cards to the end and keeping the $k$ smallest keys: a
uniformly random $k$-subset of the other cards.)

With $W$ wins, $T$ ties and $n$ trials,

$$
\bar{X} = \frac{W + T/2}{n}, \qquad
s^2 = \frac{n}{n-1}\left(\frac{W + T/4}{n} - \bar{X}^2\right), \qquad
\mathrm{SE} = \frac{s}{\sqrt{n}},
$$

and by the central limit theorem the 95% confidence interval is
$\bar{X} \pm 1.96\,\mathrm{SE}$ ([`stats.py`](../src/pokerlab/stats.py)).
Since $\operatorname{Var}(X) \le \tfrac14$, the half-width is at most $1.96/(2\sqrt{n})$:
50,000 trials give at most ±0.44 percentage points. The number of trials for a target
half-width $m$ is $n = (1.96/m)^2\, p(1-p)$.

The tests check the interval's **coverage** empirically: over many repeated
simulations of a spot with known exact equity, about 95% of the intervals contain it.

## 5. Pot odds, break-even equity and EV

Inputs: pot $P$ before the bet, the opponent's bet $B$, and the effective stack $S$
(the most either player can still put in). The hero can call at most
$c = \min(B, S)$; any excess bet is returned. Calling makes the final pot $P + 2c$.

EV is measured **relative to folding**, so $\mathrm{EV}(\text{fold}) = 0$ (chips already
in the pot are sunk). If no more betting follows,

$$
\mathrm{EV}(\text{call}) = E\,(P + 2c) - c .
$$

Setting this to zero gives the **break-even equity** and the equivalent **pot odds**:

$$
E^{*} = \frac{c}{P + 2c}, \qquad \text{pot odds} = (P + c) : c .
$$

Example: $P = 100$, $B = 50$: $E^{*} = 50/200 = 25\%$, pot odds $3:1$; with
$E = 35.2\%$, $\mathrm{EV} = 0.352 \cdot 200 - 50 = +20.4$.
([`decision.py`](../src/pokerlab/decision.py))

EV is linear in $E$, so a confidence interval $[E_{lo}, E_{hi}]$ maps directly to
$[\mathrm{EV}(E_{lo}), \mathrm{EV}(E_{hi})]$. The showdown-only verdict is *Call* if
$E_{lo} > E^{*}$, *Fold* if $E_{hi} < E^{*}$, and *Too close to call* otherwise.

## 6. Turn and river betting

The formula above is exact only when the call ends the betting (an all-in). Otherwise
the opponent can bet again on the turn and river
([`multistreet.py`](../src/pokerlab/multistreet.py)).

### The opponent's betting rule

On each later street the opponent bets $b = \min(f \cdot \text{pot}, \text{stack})$ or checks.
Rank the combos of their current range by made-hand strength on the current board.
With value share $v$ and bluff share $u$, the strongest $v$ of the range's weight
bets for value, the weakest $u(1-v)$ bets as a bluff, and the rest checks. Formally,
place the weighted combos on $[0, M]$ from strongest to weakest ($M$ = total weight);
a group of equally strong combos occupying $[\ell, h]$ bets with probability

$$
p = \frac{\big|[\ell,h] \cap [0, vM]\big| + \big|[\ell,h] \cap [M - u(1-v)M,\, M]\big|}{h - \ell}.
$$

The betting share of the range is therefore exactly $v + u(1-v)$ on every street.

### Bayesian narrowing

After the opponent bets, each combo's weight becomes $w_k\,p_k$; after a check,
$w_k(1 - p_k)$. This is Bayes' rule: $P(k \mid \text{bet}) \propto P(\text{bet} \mid k)\,P(k)$.
A bet makes the range *polarised* (strong hands and bluffs), a check makes it *capped*.

### The next card

Once the opponent's combo is fixed, each of the $n$ remaining cards is equally likely
to come next, and $n$ is the same for every combo. Hence

$$
P(\text{next card} = x) \;\propto\; \sum_{k \,:\, x \notin k} w_k ,
$$

and conditioning on $x$ removes the combos that contain $x$.

### Backward induction

Let $V$ be the expected chips the hero collects from the pot from a node onwards,
minus the chips the hero still puts in. On the river, with pot $Q$, bet size $b$,
betting weights $w^{bet}$ and checking weights $w^{chk}$ (masses $m^{bet}, m^{chk}$), and
$\sigma(w)$ the hero's weighted showdown share against weights $w$:

$$
V_{\text{river}} = \frac{m^{chk}\, Q\,\sigma(w^{chk}) + m^{bet} \max\!\big(0,\; (Q + 2b)\,\sigma(w^{bet}) - b\big)}{m^{chk} + m^{bet}} .
$$

The $\max(0, \cdot)$ is the hero's choice between folding (0) and calling. On the turn,
$\sigma$ and the call value are replaced by the expectation of $V_{\text{river}}$ over the
river card, with the pot and stack updated after a called bet. The value of calling
the current bet is

$$
\mathrm{EV}(\text{call}) = -c + \mathbb{E}\big[V_{\text{turn}}\big] .
$$

If the opponent never bets ($v = u = 0$), every $\max$ disappears and
$\mathrm{EV} = E(P + 2c) - c$ again; a test checks this identity.

The hero is assumed to know the opponent's strategy and respond optimally (a
**best response**). This is optimistic, and the app says so.

### Realised equity

The **realised equity** is the equity that would produce the multi-street EV with no
further betting:

$$
E_{\text{real}} = \frac{\mathrm{EV}_{\text{multi}} + c}{P + 2c}, \qquad
\text{realisation} = \frac{E_{\text{real}}}{E}.
$$

Realisation above 100% means the hero gains more from later bets (calling when ahead)
than they lose by folding; below 100% means later bets force them to give up pots.

## 7. Assumptions and limitations

- **Heads-up:** one opponent.
- **The range is an assumption:** results are conditional on it, and on the betting style.
- **Simple opponent model:** made-hand strength only (draws rank as weak), fixed bet size.
- **The hero never bets or raises;** facing a bet they call or fold.
- **Best response:** the hero is assumed to know the opponent's strategy.
- **No rake, no table dynamics, no multi-hand effects.**

## 8. How the maths is verified

| Claim | Test |
|---|---|
| Evaluator is correct | All 2,598,960 five-card hands: category counts and 7,462 strength classes; brute-force best-of-subsets; independent `treys` library; `hypothesis` properties |
| Fast evaluator = reference | Identical scores on every 5-card hand and on random 5/6/7-card hands |
| Exact equity is correct | Recomputed independently with `treys`; closed-form river cases |
| Monte Carlo is unbiased with valid CIs | Agreement with exact within 4 SE; empirical 95% coverage; AA vs KK ≈ 82% |
| EV and break-even | The worked example above; common bet sizes; all-in capping |
| Multi-street model | Reduces to M5 when nobody bets; closed-form results for unbeatable hands; probabilities sum to 1; matches the reference implementation |
