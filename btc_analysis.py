# btc_analysis.py
# 필요 패키지: pip install yfinance pandas numpy matplotlib scipy
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import os

plt.rcParams['figure.figsize'] = (10,6)

# 1) 데이터 다운로드 (BTC-USD, 일봉, 최대 범위)
def download_btc():
    df = yf.download("BTC-USD", start="2009-01-01", end=None, progress=False)
    df.index = pd.to_datetime(df.index)
    
    # Check the actual column structure (debug info)
    print(f"Downloaded BTC data: {df.shape[0]} rows from {df.index[0].date()} to {df.index[-1].date()}")
    print("Available columns:", df.columns.tolist())
    
    # Handle multi-level columns if they exist
    if isinstance(df.columns, pd.MultiIndex):
        # Flatten multi-level columns by taking the first level (column names)
        df.columns = df.columns.get_level_values(0)
    
    # Ensure we have the required columns
    required_cols = ['Open','High','Low','Close','Volume']
    available_cols = [col for col in required_cols if col in df.columns]
    
    if len(available_cols) != len(required_cols):
        print(f"Warning: Missing columns. Available: {df.columns.tolist()}")
        print(f"Required: {required_cols}")
        # Try to use what's available
        df = df[available_cols].dropna()
    else:
        df = df[required_cols].dropna()
    
    return df

# 2) 집계 함수 (resample)
def make_aggregates(df):
    daily = df.copy()
    weekly = df.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    monthly = df.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    yearly = df.resample('YE').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    return {'daily': daily, 'weekly': weekly, 'monthly': monthly, 'yearly': yearly}

# 3) 주요 통계 계산
def compute_stats(ohlc):
    ohlc = ohlc.copy()
    ohlc['logret'] = np.log(ohlc['Close']).diff()
    ohlc['ret'] = ohlc['Close'].pct_change()
    stats = {
        'count': len(ohlc),
        'mean_logret': ohlc['logret'].mean(),
        'std_logret': ohlc['logret'].std(),
        'median_ret': ohlc['ret'].median(),
        'pct_up': (ohlc['ret']>0).mean(),
        'avg_body': (abs(ohlc['Close']-ohlc['Open'])).mean(),
        'avg_range': (ohlc['High']-ohlc['Low']).mean()
    }
    return stats, ohlc

# 4) max drawdown
def max_drawdown(series):
    roll_max = series.cummax()
    drawdown = series/roll_max - 1.0
    mdd = drawdown.min()
    return mdd, drawdown

# 5) seasonality: month & weekday
def seasonality_tables(daily):
    d = daily.copy()
    d['month'] = d.index.month
    d['weekday'] = d.index.day_name()
    month_mean = d.groupby('month')['logret'].mean()
    weekday_mean = d.groupby('weekday')['logret'].mean().reindex(
        ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    )
    return month_mean, weekday_mean

# 6) halving impact (user-specified halving dates)
def halving_analysis(daily, halving_dates):
    out = []
    daily_close = daily['Close']
    for hd in halving_dates:
        center = pd.to_datetime(hd)
        pre = daily_close.asof(center - pd.Timedelta(days=1))
        # 6/12 months later indices:
        for months in [6,12]:
            later = center + pd.DateOffset(months=months)
            if later > daily_close.index[-1]:
                cumret = np.nan
            else:
                later_price = daily_close.asof(later)
                if np.isnan(pre) or np.isnan(later_price):
                    cumret = np.nan
                else:
                    cumret = (later_price / pre) - 1
            out.append({'halving': center.date(), 'months': months, 'cumret': cumret})
    return pd.DataFrame(out)

# ---------------- main ----------------
if __name__ == "__main__":
    df = download_btc()
    aggs = make_aggregates(df)

    # compute stats for each timeframe
    summary = {}
    for name, ohlc in aggs.items():
        s, o = compute_stats(ohlc)
        mdd, drawdown = max_drawdown(ohlc['Close'])
        s['max_drawdown'] = mdd
        summary[name] = s
        # save aggregated CSV
        o.to_csv(f'{name}_ohlc.csv')
    pd.DataFrame(summary).T.to_csv('summary_stats.csv')

    # seasonality (daily) - need to add logret column first
    daily_with_returns = aggs['daily'].copy()
    daily_with_returns['logret'] = np.log(daily_with_returns['Close']).diff()
    month_mean, weekday_mean = seasonality_tables(daily_with_returns)
    month_mean.to_csv('month_mean_logret.csv')
    weekday_mean.to_csv('weekday_mean_logret.csv')

    # halving analysis - known dates
    halving_dates = ["2012-11-28","2016-07-09","2020-05-11","2024-04-20"]
    halving_df = halving_analysis(aggs['daily'], halving_dates)
    halving_df.to_csv("halving_analysis.csv", index=False)

    # quick plots
    aggs['daily']['Close'].cummax().plot(title='BTC Close cummax (visual check)'); plt.savefig('cummax.png'); plt.clf()
    aggs['daily']['Close'].plot(title='BTC Close price'); plt.savefig('close.png'); plt.clf()

    # month heatmap (years x months) - CSV export for external plotting
    monthly = aggs['monthly'].copy()
    monthly['year'] = monthly.index.year
    monthly['month'] = monthly.index.month
    monthly['logret'] = np.log(monthly['Close']).diff()
    heat = monthly.pivot_table(values='logret', index='year', columns='month', aggfunc='sum')
    heat.to_csv('monthly_year_month_heat.csv')

    print("\n" + "="*60)
    print("🎉 Bitcoin Analysis Complete!")
    print("="*60)
    print("Generated files:")
    print("📊 Data files:")
    print("  - daily_ohlc.csv: Daily OHLCV data")
    print("  - weekly_ohlc.csv: Weekly aggregated data")
    print("  - monthly_ohlc.csv: Monthly aggregated data")
    print("  - yearly_ohlc.csv: Yearly aggregated data")
    print("📈 Analysis files:")
    print("  - summary_stats.csv: Statistical summary by timeframe")
    print("  - month_mean_logret.csv: Monthly seasonality analysis")
    print("  - weekday_mean_logret.csv: Weekly seasonality analysis")
    print("  - halving_analysis.csv: Bitcoin halving impact analysis")
    print("  - monthly_year_month_heat.csv: Year-month heatmap data")
    print("📊 Charts:")
    print("  - cummax.png: Cumulative maximum price chart")
    print("  - close.png: Bitcoin price chart")
    print("="*60)
