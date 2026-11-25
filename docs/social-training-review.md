# CashOutAi social features and training-game review

**Review date: November 25, 2026**  
**Status: source review and draft implementation; not a production-readiness approval**

CashOutAi already contains useful foundations for a learning community: profiles, shared chat, following, notifications, paper-trade history, and a visible progression system. Preserve those foundations while changing what progression rewards. The existing points system mainly rewards activity and profit; it does not establish that a member learned a skill or followed a sound process.

Owner decision: cash rewards are outside the current scope. The historical cash-prize notes below explain old source only; no cash program is being developed or activated.

This review distinguishes the original application, repairs included in this draft, and proposed work. “Implemented” means that a source path exists, not that its production configuration or security has been verified. The original reference is commit [`5702460a275cda067dba510dc4ba4432f1051359`](https://github.com/zenmillonario/ArgusAi-CashOut/tree/5702460a275cda067dba510dc4ba4432f1051359). Its [PRD](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/memory/PRD.md) describes a private team-chat application with stock paper trading. The matrix below checks those claims against code.

## 1. Implemented, partial, and absent features

Unless another file is named, backend functions in this table are in [backend/server.py](../backend/server.py).

| Feature | Source evidence and actual state | Direction |
| --- | --- | --- |
| Profile customization | **Implemented, with server privacy repair.** `ProfileCustomization.handleSave` posts bio, avatar, banner, trading-style tags, location, and visibility. The POST `update_user_profile` persists them with ownership checks; `get_user_profile` omits a hidden location from other members' responses. See [ProfileCustomization.js](../frontend/src/ProfileCustomization.js). | Keep identity and self-expression. Learning interests remain a possible extension. |
| Personal account details | **Implemented; request-model mismatch repaired in this draft.** The PUT `update_user_profile` edits real name, screen name, username, and email. It now uses `ExistingProfileUpdate` and retains `require_profile_owner`. | Keep the existing account screen; do not confuse identity editing with the separate customization POST. |
| Following and public profiles | **Implemented; client wiring and acting-member checks repaired.** `follow_user`/`unfollow_user` maintain relationship arrays and counts and create notifications. `get_user_followers`, `get_user_following`, and `get_follow_status` provide read APIs. [PublicProfile.js](../frontend/src/PublicProfile.js) and [UserList.js](../frontend/src/UserList.js) consume the appropriate responses. | Keep peer/mentor discovery. Multi-write consistency and repeatable XP remain separate weaknesses. |
| Community chat and social posts | **Shared chat implemented; separate post/feed system absent.** `Message`, `create_message`, `get_messages`, and `post_message_tasks` support stored messages, WebSocket broadcasts, replies, images, reactions, mentions, and notifications. [ChatTab.js](../frontend/src/ChatTab.js) and [ChatInput.js](../frontend/src/ChatInput.js) render the conversation. | Preserve community chat. A followed-members feed or structured journal feed would be new work. |
| Private messages and independent teams | **Absent as connected features.** No recipient/conversation model or direct-message inbox was found. The `Team` model is not connected to team-specific message routing; legacy messages broadcast globally. | Defer private messaging. Use explicitly scoped room APIs for bot conversations. |
| XP, levels, and streaks | **Implemented, with integrity gaps.** `award_xp` persists XP; `get_level_from_xp` defines five levels at 0, 500, 1,500, 5,000, and 15,000 XP. `login_user` grants 10 XP on a new UTC date and tracks consecutive login days. [XPProgressBar.js](../frontend/src/XPProgressBar.js) displays progression. | Reuse presentation; replace activity rewards with verified learning events. |
| Achievements | **Partially implemented.** `ACHIEVEMENTS` defines 16 badges. `check_achievements` and `process_login_rewards_async` contain award paths for eight: first profitable trade, chat count, heart count, referral, dedication, and three membership-duration badges. [AchievementsTab.js](../frontend/src/AchievementsTab.js) renders the catalog. | Replace or clearly label catalog-only badges before promising they can be earned. |
| Cosmetic unlocks | **Backend partial; frontend disconnected.** `update_user_theme`/`get_user_theme` gate four named themes by level. `handle_level_up` announces theme, banner, and tag unlocks, while the frontend uses a local dark/light toggle and already exposes banner/tag controls. | Cosmetic rewards suit learning progression once the rules and UI agree. |
| Leaderboard | **Absent.** No leaderboard API, score model, or ranking screen was found. UserList sorts administrators first and then names. | Build later around comparable lessons or scenarios, not existing profit totals. |
| Referrals | **Backend partial.** `register_user` accepts a code; `handle_referral_signup` links accounts and immediately increments successful referrals. Read/validation endpoints exist. No corresponding referral-entry/dashboard UI was found. | Defer promotion until a verified eligibility milestone is defined. |
| Cash prizes | **Historical bookkeeping retained; current awards disabled.** The original referral description and helper created cash-review items without a payout integration. The current referral badge has no cash promise, new cash-award creation is removed, and `review_cash_prize` rejects mutation with `410`. | Excluded from the current scope by the owner. Historical approval is not payment. |
| Stock favorites and portfolio | **Implemented legacy tools.** [FavoritesTab.js](../frontend/src/FavoritesTab.js) loads quotes; App stores symbols in per-user browser storage. `create_paper_trade`, `update_or_create_position`, `position_action`, and `calculate_user_performance` power [PortfolioTab.js](../frontend/src/PortfolioTab.js). | Preserve research/history views, but do not use the legacy ledger for trusted competitive scoring. |

The eight catalog-only achievements are Diamond Hands, Hot Streak, five profit milestones, and Diversification Master. Dedication also has a progress-display mismatch: `get_user_achievements` reads `achievement_progress.login_streak`, while login updates `daily_login_streak`. Membership checks use account age rather than verified active membership duration.

## 2. Changes already included in this draft

The earlier bounded repairs address these concrete integration errors:

1. The identity-edit PUT route now accepts `ExistingProfileUpdate`, whose fields match its implementation. Previously it accepted the customization `ProfileUpdate` model but accessed identity fields that model did not define. Session ownership and public response filtering remain intact.
2. `PublicProfile.fetchPublicProfile` reads `/users/{current_user}/follow-status/{target_user}`. Previously it expected a followers array in a profile response containing only counts, so following state was incorrect after reopening a profile.
3. `UserList.fetchFollowingList` reads `/users/{current_user}/following` and maps the returned profile objects to IDs. Both client fetch paths ignore stale responses after effect cleanup. These changes do not expand the public profile projection.

[test_profile_contract.py](../backend/tests/test_profile_contract.py) verifies accepted identity fields and persistence, ownership enforcement, explicit follow booleans, safe list shapes, and exclusion of session credentials. That earlier focused review is now included in the **181-test consolidated backend suite** passed during the November 25 release review. Isolated tests do not contact the production Mongo database, email provider, members, or devices; release build and deployment verification remain distinct from those results.

The draft also contains the five PAPER bot rooms and a separate practice ledger; its source, session, quote, and settlement boundaries are documented in [nautilus-rooms.md](nautilus-rooms.md). This review does not claim that the legacy stock ledger has acquired those guarantees.

The November 25 member-launch revision adds persistent primary navigation for Trading, Community, Notifications, Achievements and Profile on desktop and phone. Bot rooms and Stocks appear within Trading; Portfolio, stock practice, Favorites and Admin remain accessible. Community exposes a member directory and a “Share a win” shortcut that opens an editable draft and never auto-posts. Profiles retain photos, banners and following. These source changes are reflected in the private preview using clearly identified local demonstration data, not live member records.

Additional connected repairs make inbox GET requests read-only, require notification ownership, and persist reactions through the authenticated backend with correct author attribution and duplicate suppression. The member directory uses its own limited public projection rather than administrator account data. Existing earned achievements are preserved; the incomplete achievement catalog and scoring weaknesses described below have not been converted into verified training milestones. Social notifications remain inside the app; device push is restricted to Stocks alerts.

Account continuity, signup, payment activation and remembered-login findings are recorded in [member-launch-plan.md](member-launch-plan.md). Existing members must keep their IDs and accounts. The draft also prevents public registration from deleting and recreating a rejected identity.

The follow-up release review adds these bounded repairs:

- The legacy router verifies the current session's actor, administrator role where required, and supplied acting IDs. Administrative user lists, approval/role/removal operations, XP grants, diagnostics, upload, and message moderation are restricted. Private ledgers, referral details, inbox operations, and member writes cannot select another actor through a path, query, or message-author field. Intended member-visible profile, follow-list, and earned-badge reads remain available.
- Hidden locations are removed from other members' profile JSON. The owner can still read the saved value for editing.
- The historical **allow re-registration** operation now reopens the existing rejected account as pending through a guarded update. It preserves the member ID, credentials, profile, follows, history, and entitlement records, revokes the old active session, and still requires approval. It no longer deletes the account to make room for a new registration.
- Recognized legacy password hashes are verified before a guarded migration to the canonical field. A concurrent password reset cannot be overwritten by that migration. Missing hashes do not create a password bypass; working recovery email and an existing-account rehearsal remain release requirements.
- Cash award creation and approval mutation are disabled while historical records, earned XP, and badges remain. The referral badge has no cash promise.
- Frontend account callbacks and component requests are bound to the current login. Bot snapshot polls cover the visible asset and held assets, pause while the page is hidden, and restart on return. Chat polling follows the visible room. Practice polling preserves the newest revision across concurrent actions.
- Large HTTP responses use gzip. The five-room practice ledger now reconciles strict official finalized Kalshi outcomes through the bounded settlement service; this does not add settlement guarantees to the separate legacy stock journal.

The new [StocksWorkspace.js](../frontend/src/nautilus/StocksWorkspace.js) implements a research surface: manual ticker loading, a hosted TradingView chart, interval selection, browser-local watchlist and study notes, TV mode, and fullscreen. The component labels stock Nautilus guides as future work. Its embedded chart is not an application-owned historical-data API, and its ticker form is not a company-search service. Production discussion links to community chat; local preview messages do not establish a persisted stock-room service. The November 25 revision also adds a durable Stocks alert feed and explicit Stocks-only push controls using the owner-confirmed thinkorswim → Zapier route. See [stock-alert-rollout.md](stock-alert-rollout.md) for the implementation and deployment mapping. Social activity remains in-app without device push.

## 3. Remaining launch risks

### XP farming and unverified actions

Existing awards include 25 XP per submitted trade, another 50 for a profitable sale, 5 per chat message, 8 extra for replies, 2 per reaction, 10 per follow, and 25 for profile changes containing an avatar, bio, or banner. Sources are `create_paper_trade`, `post_message_tasks`, `add_message_reaction`, `follow_user`, and the customization POST route.

Follow/unfollow cycles, removing and re-adding reactions, and repeated profile changes have no permanent reward-consumption record. The direct `award_user_xp` endpoint is now administrator-restricted, but a manual award still does not establish a verified learning-completion event. `award_xp` reads a total and then sets a replacement total; concurrent updates can overwrite each other. Achievement checks award points before recording earned badges, so concurrent checks can grant points twice.

Legacy stock trades accept browser-submitted prices and quantities without a shared cash-budget ledger. Their profit totals are not comparable learning scores. Alternate position-action/close paths also do not consistently trigger the same reward logic. These are reasons to redesign scoring rather than connect a leaderboard to existing fields.

### Authorization repairs and remaining business-rule review

The original source and early draft had member/admin ID trust gaps. The current release adds a central actor-and-role gate to legacy member REST and targeted ownership/privacy repairs, described above. It also binds push registrations to the current login; see [session-and-alerts-review.md](session-and-alerts-review.md). Authenticated cross-member writes and impersonated administrator IDs are rejected in the covered routes. These repairs should not be described as a complete independent security audit or proof that every old accounting, upload-storage, reward, and moderation business rule is production-ready.

The earlier hidden-location exposure is repaired at the server projection: another member receives no hidden location value, while the profile owner can edit the saved value. Public profit and win-rate fields still need a deliberate visibility and presentation policy and must be understood as practice statistics rather than verified financial performance.

### Legacy generated-price defect and the draft repair

In the original source, `get_current_stock_price` fell back to `get_mock_stock_price` after failed provider requests. The fallback used canned or symbol-derived prices with generated daily variation. `update_positions_pnl`, `position_action`, and `close_position` used this helper, allowing unavailable market data to produce invented valuations or trigger legacy stop-loss/take-profit closes.

The November 25 draft removes both generated-price and company-profile price fallbacks from these real quote paths. A shared bounded FMP adapter preserves observation and receipt time separately and coalesces duplicate requests within one server process. Unavailable data preserves the previous position value with an unavailable status. Because the current FMP last-price integration does not establish execution eligibility, automatic stock stop/target closes and quote-based fills are paused; an explicit manual journal price remains self-reported. The separate binary-contract practice ledger is unaffected. See [quote-service-review.md](quote-service-review.md) for the exact contract and limitations.

### Historical cash-reward notes — excluded from the current scope

In the original source, referral success was counted at registration, before approval or another verified eligibility event. The [original cash-prize helper](https://github.com/zenmillonario/ArgusAi-CashOut/blob/5702460a275cda067dba510dc4ba4432f1051359/backend/cash_prize.py) pushed pending items into the user record. The old `review_cash_prize` implementation added an approved item and incremented earned totals before separately removing pending state. Its input model lacked nonnegative/maximum-prize constraints, and the approval sequence was not a one-time atomic transition.

Those are historical findings, not current enabled award behavior. The release removes new cash-award creation, disables the approval mutation, and retains historical records without presenting them as money paid. Any future cash program would need its own approved eligibility, amount, audit, duplicate-protection, and payout design. No such program or payout workflow is being activated here.

## 4. Recommended training-game direction — proposed

Use a simple learning loop: **observe, decide, explain, practice, review**. A member studies a chart, records a thesis and what would invalidate it, chooses an action or passes, then reviews the result. A correct pass should be a valid learning outcome; progression should not require continuous trading.

Start with lessons tied to the actual interface: interpreting a bid/ask spread, distinguishing cash from equity, understanding fees, sizing a practice entry, comparing an exit with the original plan, and recognizing that an expired contract requires an official outcome. Keep P&L visible as feedback without making profit the principal source of XP.

Verified lesson XP needs a server-owned completion record containing user, lesson/version, checkpoint or scenario, attempt, evidence, timestamp, and awarded amount. The client submits an answer or action; the server decides whether a defined checkpoint passed. A unique completion/reward key and atomic update prevent duplicate grants. Cap repeatable practice rewards. A $100 account reset must not reset previously consumed lesson awards.

Useful early badges could recognize completing the spread lesson, writing and reviewing a plan, identifying missing data, or finishing a weekly study session. These are proposals, not implemented badges. Preserve avatars, following, community discussion, and cosmetic rewards as community features. Avoid XP for message count, follower churn, trade volume, or profit alone.

Later, offer opt-in challenges with the same historical scenario, starting conditions, rules, and scoring rubric for every participant. Compare completion and decision quality before adding rankings. Keep private study notes private by default and make sharing an explicit action.

## 5. Staged stock Nautilus data requirements

### Stage A: research workspace — draft UI exists

Retain ticker loading, chart exploration, watchlists, notes, and fullscreen. `StockMarketChart` embeds a provider-hosted chart and displays a possible-delay notice. Chart availability does not prove that CashOutAi can retrieve bars for analysis, execution, or replay. Browser-local notes and favorites are not cross-device member persistence.

The original `/api/stock/{symbol}` route tried FMP quote and profile endpoints and labelled retrieval time as `timestamp`. The draft now routes it through the shared FMP quote adapter, preserving provider time or an explicit missing/invalid-time state. It does not claim a last-price quote proves live executable bid/ask, an open market or commercial display rights. Current entitlement, multi-process collection and streaming distribution remain to be connected. Published cost and coverage options are compared in [realtime-quotes-and-launch.md](realtime-quotes-and-launch.md).

Live activation still requires the actual Windows PAPER publishers, the coordinated Zapier secret/identity mapping, Firebase device delivery checks, and current stock-data entitlement. Recorded preview packets, isolated tests, gzip, and reduced browser polling do not establish those external integrations. Keep the existing Assistro branch during adoption and verify recovery email before an account-security cutover.

### Stage B: dependable server data — future work

No historical OHLC/candle or company/ticker-search backend was found in the reviewed legacy source. Add explicit adapters rather than extracting data from the embedded chart. A search result needs a stable instrument identity, symbol, exchange, name, currency, and asset type; a manual ticker string alone does not resolve ambiguous listings.

Quotes need provider/source, provider timestamp, retrieval time, and explicit live/delayed/replay/unavailable status. Bars need interval, timestamp/timezone, open/high/low/close/volume, and declared adjustment and trading-session policy. Validate ordering, duplicates, gaps, and impossible prices. Verify provider access, rate limits, and permitted use before promising coverage. An unavailable response must remain unavailable rather than silently changing data source to a simulation.

### Stage C: stock Nautilus and guided replay — future work

Specify what Nautilus calculates from stock data, its required history, update cadence, and behavior when data is incomplete. Label computed studies separately from model signals and market prices. Historical replay must reveal only information available at the simulated time and retain a versioned scenario for reproducible evaluation.

If stock execution practice is added, define a stock-specific ledger: supported share quantities, cash constraints, fill assumptions, fees, sessions, corporate actions, and reset/history rules. Binary-contract payout and settlement rules cannot simply be applied to shares. Connect verified lesson events only after those data and accounting contracts are tested.

The immediate product opportunity is a coherent research and learning community. Trusted scoring, stock Nautilus, and historical challenges have separate implementation and verification work remaining. Cash rewards remain outside the agreed scope.
