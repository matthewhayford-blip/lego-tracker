# Retired & Rare: tone of voice

**For:** anyone writing copy for this site (page text, emails, social posts, PR
descriptions), human or Claude.

This is a companion to `HANDOVER.md`, not a replacement for it. HANDOVER covers what
the site is and isn't (retirement and deals, never investment; no false precision on
dates). This doc covers how it talks.

---

## Who's talking

One person, not a company. Matt, a LEGO collector in the UK, built and runs this
himself. The copy should read like him explaining something he actually knows about to
someone he wants to help, not like a brand, not like a team, and not like a tool
generating on-brand content. "About" already says this outright ("There is no company
behind it and no team"); everything else should sound consistent with that being true.

## The five traits

**Plainspoken.** Short sentences over long ones. Ordinary words over dressed-up ones.
"We don't have a live UK price for this set yet" beats "Live pricing data for this
product is not currently available." If a sentence needs reading twice, rewrite it, not
the reader's attention span.

**Evidence-first, confidence-calibrated.** Every claim on this site either comes from a
named source (Brick Fanatics, the Dobrynskaya & Kishilova paper, a live retailer feed)
or is flagged as a model. Say what's known, say what's estimated, and never blur the
two together. "Expected to retire around the end of 2026" is honest. "Retiring in 116
days" is not, because nobody actually knows the day.

**Modest, not hedgy.** Being honest about uncertainty is not the same as qualifying
every sentence into mush. Say the thing plainly, then name the caveat once, clearly.
Don't wrap it in "may potentially" and "in some cases" until it says nothing. "Sets in
this theme have historically appreciated around 11% a year" is modest. "Sets in this
theme may, in certain circumstances, potentially see some degree of appreciation" is
hedgy, and it's also a tell that no one edited it.

**Useful before persuasive.** The job of every page is to help someone decide whether
to buy now, wait, or not bother, not to talk them into anything. Cut any sentence that
exists only to build excitement rather than convey information. If a line would work
equally well on a listing for a different set, it's filler; make it specific to this
one.

**Unimpressed by itself.** No "revolutionary," no "unlock," no "elevate your
collection," no exclamation marks doing the enthusiasm's job for it. If the numbers are
good, show the numbers. They don't need a hype word standing next to them.

## What this sounds like, side by side

**Don't:**
> In today's fast-moving collectibles market, LEGO sets aren't just toys — they're
> genuine investment opportunities! Not only do retired sets become harder to find,
> but their value can skyrocket, making now the perfect time to secure your favourites
> before it's too late.

**Do:**
> Once a set stops being sold, the only supply left is whatever people already own.
> Sealed sets that were easy to find at RRP get harder to find at any price. Knowing
> the retirement window matters more than knowing the exact day.

The first one oversells (investment framing this project deliberately avoids), hedges
nothing while claiming everything ("skyrocket"), and reads like eleven other
collectibles sites. It also uses an em dash, the thing this whole guide bans. The
second says one true thing plainly and stops.

**Don't:**
> This model leverages a robust, data-driven methodology to project potential future
> valuations, taking into account a variety of key factors that may influence
> long-term appreciation trends.

**Do:**
> The model is anchored to a study of 2,322 retired sets: about 11% average annual
> appreciation, adjusted for set size and a few other things we can name. It's a
> model, not a forecast. See how we calculate it.

The first is true of literally any model and says nothing you could disagree with. The
second gives a real number, a real source, and an honest limit. That's the whole house
style in one sentence.

## Mechanics

**No em dashes.** Use a comma, a full stop, or parentheses instead. This is the single
easiest tell that something wasn't actually written by a person thinking in their own
voice, and it's banned outright. Not "avoid where possible": banned. If a sentence
needs one to hold together, it's two sentences.

**Skip the other AI tells too**, the same way: constructions like "it's not just X,
it's Y"; sentences that open with "Additionally," "Furthermore," or "In conclusion";
rule-of-three adjective lists ("fast, reliable, and seamless"); and rhetorical
questions used as a transition ("But what does this mean for you?"). None of these are
wrong on their own. They're just what unedited AI copy defaults to, and once you notice
the pattern you can't stop seeing it. Read a paragraph back and cut anything that
sounds like it could open a SaaS landing page.

**Contractions are fine.** "Don't," "it's," "we don't have": this is a person talking,
not a legal notice. The trust/privacy/method pages can be a little more formal because
they're doing a different job, but even there, plain beats stiff.

**Numbers do the talking.** Money, percentages and dates are already handled by
`config.money()` and `date_phrase()` in the build. Don't restate a number in prose if
the surrounding markup already shows it; refer to it ("the price above," "that model")
instead of duplicating it in words.

**Name the source or name the uncertainty, every time.** "Reported by fan media, not
announced by LEGO." "This is a model, not a forecast." "We don't have a live UK price
for this set yet." These aren't disclaimers bolted on for legal cover. They're the
actual difference between this site and a hype account, so they belong in the same
sentence as the claim, not in small print underneath it.

## A quick self-edit pass

Before publishing anything, read it back once for:

1. Any em dash. Replace it. (This doc had eighteen of them in its first draft, in the
   very document banning them. Check your own work; the rule catches its author too.)
2. Any sentence that oversells, hedges into mush, or would read the same on a
   different set's page. Cut it or make it specific.
3. Any claim without a source or a stated confidence. Add one, or soften the claim.
4. Any word from the banned list: revolutionary, unlock, elevate, journey, seamless,
   game-changing, must-have, don't miss out.
5. Read it aloud. If it doesn't sound like a person who collects LEGO explaining
   something to a friend, rewrite it.
