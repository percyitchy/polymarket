# Poly Eye - Polymarket Builders Program Application

## 🎯 Project Overview

**Project Name:** Poly Eye  
**Tagline:** "See What Smart Money Sees"  
**Website:** [Coming Soon]  
**Email:** [Your Email]  
**X Handle:** [Your X Handle]  
**Telegram:** [Your Telegram Handle]

### Mission Statement

Poly Eye is an advanced trading signals platform that aggregates and analyzes on-chain trading activity from Polymarket's most successful traders. We provide real-time, actionable trading signals by monitoring consensus patterns, whale movements, insider activity, and order flow dynamics across the Polymarket ecosystem.

### Value Proposition

While Polymarket provides the infrastructure for prediction markets, traders lack visibility into what successful traders are doing in real-time. Poly Eye bridges this gap by:

1. **Tracking Elite Traders**: Monitoring 200+ wallets with proven track records (70%+ win rate, $25K+ volume, 12+ markets)
2. **Real-Time Signal Detection**: Identifying consensus patterns, whale positions, and insider activity as they happen
3. **Multi-Signal Intelligence**: Combining multiple signal types for higher confidence trades
4. **Gasless Trading Integration**: Enabling users to act on signals instantly through Builder Program relayer

---

## 📊 Core Technology Stack

### Data Sources & APIs

- **Polymarket Data API**: Real-time trade data, closed positions, market information
- **Polymarket CLOB API**: Order book data, price feeds, market status
- **Gamma API**: Market metadata, event information, outcome prices
- **HashiDive API**: Trader analytics and performance metrics
- **Polymarket Analytics API**: Leaderboard data and trader rankings
- **Custom Wallet Database**: SQLite database with 200+ tracked wallets

### Infrastructure

- **Backend**: Python 3.11+ with async processing
- **Database**: SQLite with optimized indexes for real-time queries
- **Monitoring**: 7-second polling interval for wallet trades
- **Notifications**: Telegram Bot API with topic-based routing
- **Queue System**: Parallel worker processing (7 workers) for wallet analysis

---

## 🔔 Signal Types (10 Core Signals)

### 1. **Consensus Alpha Signals** ⭐ (Primary Signal)

**Description**: Detects when 3+ elite traders (70%+ win rate, $25K+ volume) buy the same market outcome within a 15-minute window.

**Technical Implementation**:
- Monitors 200+ tracked wallets every 7 seconds
- Maintains rolling 15-minute windows per market/outcome
- Filters by wallet quality metrics (win rate, volume, ROI)
- Validates market status (active, not resolved)
- Price divergence checks (≤25% for $0.05-$0.5, ≤10% for ≥$0.5)

**Signal Strength Indicators**:
- **Weak**: 3 wallets, <$5K total position
- **Moderate**: 4-5 wallets, $5K-$10K total position
- **Strong**: 6+ wallets, >$10K total position
- **Very Strong**: Includes A-list traders (top performers)

**Use Case**: Best for identifying high-probability trades where multiple successful traders agree on direction.

---

### 2. **A-List Trader Consensus** ⭐⭐ (Premium Signal)

**Description**: Detects when 2+ A-list traders (top 1% performers by volume/profit) enter the same position.

**Technical Implementation**:
- Identifies A-list traders from weekly/monthly leaderboards
- Tracks category-specific performance (Politics, Sports, Crypto, etc.)
- Requires 2+ A-list traders for signal
- Routes to premium Telegram topic

**Signal Strength**: Very High (A-list traders have exceptional track records)

**Use Case**: Premium signals for users who want to follow only the absolute best traders.

---

### 3. **Whale Position Alerts** 🐋

**Description**: Detects large position entries/exits (>$10K) from tracked wallets.

**Technical Implementation**:
- Monitors position size changes in real-time
- Calculates USD value of positions
- Distinguishes between entry and exit signals
- Tracks whale wallet behavior patterns

**Signal Types**:
- **Whale Entry**: Large position opened (bullish signal)
- **Whale Exit**: Large position closed (bearish signal)

**Use Case**: Following smart money movements - whales often have better information or timing.

---

### 4. **Open Interest (OI) Spike Detection** 📈

**Description**: Identifies sudden increases in open interest (>50% spike) indicating strong conviction.

**Technical Implementation**:
- Monitors OI changes across all markets
- Calculates percentage change over time windows
- Correlates with consensus signals for confirmation
- Filters false positives (small markets, low liquidity)

**Signal Strength**:
- **Moderate**: 50-100% OI spike
- **Strong**: 100-200% OI spike
- **Very Strong**: 200%+ OI spike + consensus confirmation

**Use Case**: Confirming consensus signals - OI spikes indicate strong market conviction.

---

### 5. **Order Flow Analysis** 📊

**Description**: Analyzes buy/sell pressure and order book dynamics to predict price movements.

**Technical Implementation**:
- Monitors CLOB order book depth
- Calculates bid/ask imbalance
- Tracks large order placements
- Identifies order flow patterns

**Signal Types**:
- **Buy Pressure**: Strong buy orders vs. sell orders
- **Sell Pressure**: Strong sell orders vs. buy orders
- **Order Flow Confirmed**: Combines with consensus for high-confidence signals

**Use Case**: Timing entries - order flow can predict short-term price movements.

---

### 6. **Insider Pattern Detection** 🔍

**Description**: Identifies suspicious trading patterns that may indicate insider information.

**Technical Implementation**:
- Detects new wallets with large positions (>$5K)
- Identifies high win rate on first trades (>80%)
- Finds concentrated trading patterns (single market focus)
- Tracks unusual timing (before major events)

**Signal Types**:
- **New Wallet Large Position**: New address with significant position
- **High Win Rate New Wallet**: New wallet with exceptional early performance
- **Concentrated Trading**: Unusual focus on specific markets

**Use Case**: Following potential insider activity - high-risk, high-reward signals.

---

### 7. **Category-Specific Consensus** 🎯

**Description**: Detects consensus within specific market categories (Politics, Sports, Crypto, etc.).

**Technical Implementation**:
- Classifies markets by category using ML classifier
- Tracks category-specific trader performance
- Identifies consensus within category experts
- Routes signals to category-specific channels

**Categories**:
- Politics
- Sports
- Crypto
- Economics
- Entertainment
- Technology

**Use Case**: Following experts in specific domains - traders often specialize in certain categories.

---

### 8. **Size-Based Signal Routing** 💰

**Description**: Routes signals based on total position size for different user segments.

**Technical Implementation**:
- Calculates total USD position size
- Routes to different Telegram topics:
  - **Low Size** (<$10K): Standard signals
  - **High Size** (≥$10K): Premium signals
- Allows users to filter by signal strength

**Use Case**: Users can subscribe to signals matching their risk tolerance and capital.

---

### 9. **Multi-Timeframe Consensus** ⏰

**Description**: Detects consensus patterns across different time windows (5min, 15min, 1hr).

**Technical Implementation**:
- Maintains multiple rolling windows per market
- Identifies consensus patterns at different timeframes
- Provides signal confidence based on timeframe agreement
- Filters conflicting signals across timeframes

**Signal Types**:
- **Short-term** (5min): Quick trades, high frequency
- **Medium-term** (15min): Standard consensus signals
- **Long-term** (1hr): Trend confirmation signals

**Use Case**: Different trading strategies - scalping vs. swing trading.

---

### 10. **News Correlation Signals** 📰

**Description**: Correlates trading signals with news events and social media activity.

**Technical Implementation**:
- Integrates with news APIs (Alpha Vantage, custom sources)
- Monitors social media mentions (Twitter/X)
- Correlates news events with trading activity
- Provides context for consensus signals

**Signal Types**:
- **News-Driven Consensus**: Consensus after major news
- **Pre-News Activity**: Unusual trading before news release
- **Social Sentiment**: Trading aligned with social media sentiment

**Use Case**: Understanding why traders are taking positions - fundamental analysis support.

---

## 🚀 Additional Features & Functionalities

### 1. **Real-Time Dashboard** 📊

**Features**:
- Live signal feed with filtering options
- Wallet performance metrics
- Market heatmap showing consensus activity
- Historical signal performance tracking
- Win rate statistics by signal type

**Technology**: React/Next.js frontend with WebSocket connections for real-time updates

**Monetization**: Premium dashboard access for Pro subscribers

---

### 2. **Signal Performance Analytics** 📈

**Features**:
- Track signal accuracy over time
- Win rate by signal type
- ROI calculation for signals
- False positive analysis
- Signal quality scoring

**Implementation**: Backend analytics engine with historical data storage

**Value**: Helps users understand which signals are most reliable

---

### 3. **User Feed & Social Features** 👥

**Features**:
- Personalized signal feed based on user preferences
- Follow specific wallets or traders
- Comment and discuss signals
- Share signals with community
- Reputation system for signal quality

**Technology**: Social feed backend with user profiles and interactions

**Monetization**: Premium features for power users

---

### 4. **SDK & API Access** 🔌

**Features**:
- RESTful API for programmatic access
- Python SDK for easy integration
- WebSocket API for real-time signals
- Rate limiting and authentication
- Webhook support for custom integrations

**API Endpoints**:
- `/api/v1/signals` - Get recent signals
- `/api/v1/wallets` - Wallet information
- `/api/v1/markets` - Market data
- `/api/v1/consensus` - Consensus detection
- `/ws/signals` - WebSocket for real-time signals

**Monetization**: API access tiers (Free, Pro, Enterprise)

---

### 5. **Gasless Trading Integration** ⛽

**Features**:
- One-click trading from signals
- Gasless transactions via Builder Program relayer
- Safe wallet deployment for users
- Batch order execution
- Position management interface

**Technology**: Integration with Polymarket Builder Relayer Client

**Value**: Users can act on signals instantly without gas fees

**Monetization**: Transaction fees or subscription model

---

### 6. **Portfolio Tracking** 💼

**Features**:
- Track positions opened from signals
- P&L calculation
- Performance metrics
- Trade history
- Export to CSV/Excel

**Technology**: User portfolio database with position tracking

**Monetization**: Premium feature for Pro users

---

### 7. **Alert Customization** 🔔

**Features**:
- Custom alert rules (min consensus, wallet filters)
- Multiple notification channels (Telegram, Email, SMS, Push)
- Alert frequency controls
- Category filtering
- Size threshold customization

**Technology**: User preference system with notification routing

**Monetization**: Advanced customization for Pro users

---

### 8. **Mobile App** 📱

**Features**:
- Native iOS and Android apps
- Push notifications for signals
- Quick trade execution
- Portfolio tracking
- Signal history

**Technology**: React Native or native development

**Monetization**: App subscriptions

---

### 9. **Backtesting & Strategy Builder** 🧪

**Features**:
- Backtest signal strategies
- Historical signal performance
- Strategy optimization
- Paper trading mode
- Risk management tools

**Technology**: Backtesting engine with historical data

**Monetization**: Premium feature for advanced users

---

### 10. **Integration Marketplace** 🔗

**Features**:
- Integrations with trading bots
- Discord bot integration
- TradingView alerts
- Zapier/IFTTT connections
- Custom webhook integrations

**Technology**: Integration framework with plugin system

**Monetization**: Revenue share with integration partners

---

## 💰 Monetization Strategy

### Tier 1: Free Plan
- Basic consensus signals (3+ wallets)
- 24-hour delay on premium signals
- Limited signal history
- Basic dashboard access

### Tier 2: Pro Plan ($29/month)
- All signal types
- Real-time signals
- Full dashboard access
- Portfolio tracking
- API access (limited)
- Custom alerts

### Tier 3: Premium Plan ($99/month)
- All Pro features
- A-list trader signals
- Insider pattern detection
- Advanced analytics
- Priority API access
- Gasless trading integration
- Mobile app access

### Tier 4: Enterprise Plan (Custom)
- Custom integrations
- Dedicated support
- White-label options
- Custom signal development
- Volume discounts

### Additional Revenue Streams
- Transaction fees on gasless trades (1-2%)
- API usage fees
- Affiliate commissions
- Sponsored signals (clearly marked)
- Data licensing to institutions

---

## 🎯 Polymarket Builders Program Integration

### Why We're a Perfect Fit

1. **Volume Generation**: We route trades from users following our signals, generating significant volume for Polymarket
2. **User Acquisition**: We bring new traders to Polymarket through our signals platform
3. **Liquidity Provision**: Our users add liquidity to markets through consensus-driven trading
4. **Data Attribution**: We properly attribute all orders through Builder API keys

### Builder Program Benefits We'll Leverage

#### 1. **Polygon Relayer Access** ⛽

**Implementation**:
- Integrate `@polymarket/builder-relayer-client` (TypeScript) or `py-builder-relayer-client` (Python)
- Deploy Safe Wallets for users who want gasless trading
- Route all user trades through Polymarket relayer
- Pay gas fees on behalf of users (covered by transaction fees)

**Value Proposition**:
- Users can act on signals instantly without gas fees
- Lower barrier to entry for new traders
- Better user experience = more volume

**Technical Setup**:
```python
from polymarket_builder_relayer_client import RelayClient
from polymarket_builder_signing_sdk import BuilderConfig, BuilderApiKeyCreds

# Configure builder credentials
builder_creds = BuilderApiKeyCreds(
    key=os.getenv("BUILDER_API_KEY"),
    secret=os.getenv("BUILDER_SECRET"),
    passphrase=os.getenv("BUILDER_PASSPHRASE")
)

builder_config = BuilderConfig(localBuilderCreds=builder_creds)

# Initialize relayer client
relayer_url = "https://relayer-v2.polymarket.com/"
client = RelayClient(relayer_url, chain_id=137, wallet=user_wallet, builder_config=builder_config)

# Deploy Safe wallet for user
safe_response = await client.deploySafe()
```

---

#### 2. **Order Attribution** 🏷️

**Implementation**:
- Add Builder API headers to all orders routed through our platform
- Use remote signing server for security (recommended approach)
- Attribute orders properly for Builder Leaderboard tracking

**Technical Setup**:
```python
# Remote signing configuration (recommended)
builder_config = BuilderConfig(
    remoteBuilderConfig={
        "url": "https://api.polyeye.com/sign",
        "token": "user-auth-token"
    }
)

# Local signing (if we control entire flow)
builder_config = BuilderConfig(
    localBuilderCreds=builder_creds
)

# Create order with builder attribution
order = await clob_client.createOrder({
    "price": signal_price,
    "side": signal_side,
    "size": user_position_size,
    "tokenID": market_token_id
})

# Post order with builder headers automatically added
response = await clob_client.postOrder(order)
```

**Attribution Headers** (automatically added by SDK):
- `POLY_BUILDER_API_KEY`: Our builder API key
- `POLY_BUILDER_TIMESTAMP`: Unix timestamp
- `POLY_BUILDER_PASSPHRASE`: Builder passphrase
- `POLY_BUILDER_SIGNATURE`: HMAC signature

---

### Critical Requirements for Builder Program Success

#### ✅ **Must-Have Requirements**

1. **Builder API Keys** 🔑
   - Obtain Builder API credentials from Polymarket
   - Set up secure storage (environment variables, secrets manager)
   - Never expose keys in client-side code

2. **Order Attribution** 📊
   - Implement proper order attribution for ALL user trades
   - Use official SDKs (@polymarket/builder-signing-sdk)
   - Track attribution metrics for reporting

3. **Relayer Integration** ⛽
   - Integrate Polygon relayer for gasless transactions
   - Deploy Safe Wallets for users
   - Handle transaction states properly (STATE_NEW → STATE_CONFIRMED)

4. **Volume Generation** 📈
   - Generate significant trading volume through signals
   - Target: $100K+ monthly volume within 3 months
   - Track volume metrics for Builder Leaderboard

5. **User Experience** 🎨
   - Seamless integration of gasless trading
   - Clear attribution of orders
   - Fast transaction execution

---

#### ⚠️ **Critical Considerations & Challenges**

1. **Security Concerns** 🔒
   - **Challenge**: Builder API keys must be kept secure
   - **Solution**: Use remote signing server (recommended approach)
   - **Implementation**: Deploy secure signing server, never expose keys to clients

2. **Transaction Costs** 💰
   - **Challenge**: Gas fees for Safe Wallet deployment and transactions
   - **Solution**: Polymarket covers gas fees when using Safe Wallets
   - **Consideration**: Monitor transaction costs, optimize batch operations

3. **Attribution Accuracy** 📊
   - **Challenge**: Ensuring all orders are properly attributed
   - **Solution**: Use official SDKs, test attribution endpoints
   - **Monitoring**: Track attribution success rate, fix any missed attributions

4. **Volume Requirements** 📈
   - **Challenge**: Need significant volume to rank on Builder Leaderboard
   - **Solution**: Focus on user acquisition, provide value through signals
   - **Strategy**: Free tier to attract users, premium features for power users

5. **Competition** 🏆
   - **Challenge**: Many builders competing for grants
   - **Solution**: Differentiate through unique signal types and quality
   - **Focus**: A-list trader signals, insider detection, multi-signal intelligence

6. **Technical Complexity** 🔧
   - **Challenge**: Integrating multiple systems (signals, relayer, attribution)
   - **Solution**: Use official SDKs, follow documentation closely
   - **Testing**: Comprehensive testing before production launch

---

### Builder Leaderboard Strategy 🏅

**Goal**: Rank in top 10 builders for weekly/monthly volume

**Tactics**:
1. **User Acquisition**: Free tier to attract users, convert to paid
2. **Volume Incentives**: Lower fees for high-volume users
3. **Signal Quality**: Focus on high-accuracy signals to retain users
4. **Marketing**: Promote through crypto Twitter, Discord communities
5. **Partnerships**: Integrate with other DeFi platforms

**Metrics to Track**:
- Daily/weekly/monthly trading volume
- Number of attributed orders
- User acquisition rate
- User retention rate
- Signal accuracy
- Builder Leaderboard ranking

**API Endpoints for Tracking**:
- `/api-reference/builders/get-aggregated-builder-leaderboard` - Leaderboard rankings
- `/api-reference/builders/get-daily-builder-volume-time-series` - Volume trends

---

## 📋 Implementation Roadmap

### Phase 1: Core Signal Platform (Weeks 1-4)
- ✅ Existing: Consensus detection, wallet monitoring
- 🔄 Enhance: Add A-list trader detection
- 🔄 Add: OI spike detection
- 🔄 Add: Order flow analysis

### Phase 2: Builder Program Integration (Weeks 5-8)
- 🔄 Obtain Builder API keys
- 🔄 Integrate Builder Relayer Client
- 🔄 Implement order attribution
- 🔄 Deploy Safe Wallet system
- 🔄 Test gasless trading flow

### Phase 3: User Interface (Weeks 9-12)
- 🔄 Build web dashboard
- 🔄 Implement real-time signal feed
- 🔄 Add portfolio tracking
- 🔄 Create user authentication system

### Phase 4: Advanced Features (Weeks 13-16)
- 🔄 Add mobile app
- 🔄 Implement API/SDK
- 🔄 Add backtesting tools
- 🔄 Create integration marketplace

### Phase 5: Scale & Optimize (Weeks 17-20)
- 🔄 Optimize for volume
- 🔄 Marketing and user acquisition
- 🔄 Monitor Builder Leaderboard
- 🔄 Iterate based on feedback

---

## 🎯 Success Metrics

### Builder Program Metrics
- **Volume**: $100K+ monthly trading volume
- **Ranking**: Top 10 on Builder Leaderboard
- **Attribution**: 100% order attribution accuracy
- **Users**: 1,000+ active users within 6 months

### Platform Metrics
- **Signals**: 100+ signals per day
- **Accuracy**: 65%+ signal win rate
- **Users**: 5,000+ registered users
- **Revenue**: $10K+ monthly recurring revenue

---

## 📞 Contact & Next Steps

**Email**: [Your Email]  
**X/Twitter**: [Your Handle]  
**Telegram**: [Your Handle]  
**Discord**: [Your Server]

### Immediate Next Steps

1. **Apply for Builder Program** 📝
   - Submit application through builders.polymarket.com
   - Provide project details and use case
   - Request Builder API keys

2. **Technical Preparation** 🔧
   - Set up remote signing server
   - Prepare for relayer integration
   - Test order attribution flow

3. **Community Building** 👥
   - Build waitlist for beta launch
   - Engage with Polymarket community
   - Share signal insights on social media

4. **Partnership Discussions** 🤝
   - Reach out to Polymarket team
   - Discuss integration details
   - Plan launch strategy

---

## 📚 References & Documentation

- [Polymarket Builders Program](https://docs.polymarket.com/developers/builders/builder-intro)
- [Builder Profile & Keys](https://docs.polymarket.com/developers/builders/builder-profile)
- [Order Attribution](https://docs.polymarket.com/developers/builders/order-attribution)
- [Relayer Client](https://docs.polymarket.com/developers/builders/relayer-client)
- [Builder Signing Server](https://docs.polymarket.com/developers/builders/builder-signing-server)
- [Builder Leaderboard](https://builders.polymarket.com/)
- [Builder Relayer Client (TypeScript)](https://github.com/Polymarket/builder-relayer-client)
- [Builder Relayer Client (Python)](https://github.com/Polymarket/py-builder-relayer-client)
- [Builder Signing SDK](https://github.com/Polymarket/builder-signing-sdk)
- [Builder Signing Server](https://github.com/Polymarket/builder-signing-server)

---

**Disclaimer**: This document outlines our vision for Poly Eye. Actual implementation may vary based on technical constraints, market conditions, and Builder Program requirements. All trading involves risk. Past performance does not guarantee future results.

