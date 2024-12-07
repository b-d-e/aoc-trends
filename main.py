# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pandas",
#     "matplotlib",
#     "seaborn",
#     "numpy",
# ]
# ///

import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np
import argparse

def anonymise_name(name, index):
    return f"Participant {index}"

def parse_completion_data(data, anonymise=False):
    """Extract and parse completion data for each participant"""
    all_completions = []

    # Create mapping of real names to anonymous names if needed
    if anonymise:
        active_members = [(member_id, member['name'] if member['name'] else f"Anon {member_id}")
                         for member_id, member in data['members'].items()
                         if member['stars'] > 0]
        # Sort by local score to maintain consistent anonymization
        active_members.sort(key=lambda x: data['members'][x[0]]['local_score'], reverse=True)
        name_mapping = {name: anonymise_name(name, i+1)
                       for i, (_, name) in enumerate(active_members)}

    for member_id, member in data['members'].items():
        name = member['name'] if member['name'] else f"Anonymous ({member_id})"
        stars = member['stars']
        local_score = member['local_score']

        if stars == 0:
            continue

        if anonymise:
            name = name_mapping[name]

        for day, day_data in member['completion_day_level'].items():
            for star, star_data in day_data.items():
                all_completions.append({
                    'name': name,
                    'day': int(day),
                    'star': int(star),
                    'timestamp': datetime.fromtimestamp(star_data['get_star_ts']),
                    'stars_total': stars,
                    'local_score': local_score
                })

    return pd.DataFrame(all_completions)

def create_visualizations(df):
    plt.style.use('bmh')

    # Create figure with custom gridspec layout
    fig = plt.figure(figsize=(20, 15))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.5, 1])
    year = df['timestamp'].dt.year.iloc[0]
    fig.suptitle(f'Advent of Code {year} Progress', fontsize=20, y=0.98)

    # 1. Progress over time (spans all columns on top)
    ax1 = fig.add_subplot(gs[0, :])
    participants = df.groupby('name')['stars_total'].max().sort_values(ascending=False).index
    lines = {}
    scatter_points = {}

    for name in participants:
        user_data = df[df['name'] == name].sort_values('timestamp')
        line, = plt.plot(user_data['timestamp'],
                        range(1, len(user_data) + 1),
                        alpha=0.7,
                        label=name)
        scatter = plt.scatter(user_data['timestamp'],
                            range(1, len(user_data) + 1),
                            picker=True)
        lines[name] = line
        scatter_points[name] = scatter

    plt.title('Star Collection Progress Over Time', loc='left')
    plt.xlabel('Date')
    plt.ylabel('Number of Stars')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

    # Create annotation object
    annot = ax1.annotate("", xy=(0,0), xytext=(10,10),
                        textcoords="offset points",
                        bbox=dict(boxstyle="round", fc="w", ec="0.5", alpha=0.9),
                        visible=False)

    def hover(event):
        if event.inaxes == ax1:
            for name, scatter in scatter_points.items():
                cont, ind = scatter.contains(event)
                if cont:
                    x, y = scatter.get_offsets()[ind["ind"][0]]
                    timestamp = pd.Timestamp(x)
                    stars = y
                    annot.xy = (x, y)
                    text = f"{name}\n{timestamp:%Y-%m-%d %H:%M}\nStars: {stars}"
                    annot.set_text(text)
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                    return
            annot.set_visible(False)
            fig.canvas.draw_idle()

    # Bottom row plots
    # 2. Heatmap
    ax2 = fig.add_subplot(gs[1, 0])
    ordered_names = df.groupby('name')['local_score'].first().sort_values(ascending=False).index
    pivot_df = pd.crosstab(df['name'], df['day'])
    pivot_df = pivot_df.reindex(ordered_names)
    sns.heatmap(pivot_df, cmap='YlOrRd',
                cbar_kws={'label': 'Stars per Day'})
    plt.title('Stars Completed by Day', loc='left')

    # 3. Local scores
    ax3 = fig.add_subplot(gs[1, 1])
    scores = df.groupby('name')['local_score'].first().sort_values(ascending=True)
    bars = plt.barh(range(len(scores)), scores.values)
    plt.yticks(range(len(scores)), scores.index)
    plt.title('Local Scores', loc='left')
    plt.xlabel('Score')

    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax3.text(width, bar.get_y() + bar.get_height()/2,
                f'{int(width)}',
                ha='left', va='center', fontweight='bold')

    # 4. Stars per day
    ax4 = fig.add_subplot(gs[1, 2])
    day_counts = df.groupby('day').size()
    bars = plt.bar(day_counts.index, day_counts.values)
    plt.title('Total Stars Collected per Day', loc='left')
    plt.xlabel('Day')
    plt.ylabel('Number of Stars')

    for bar in bars:
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2, height,
                f'{int(height)}',
                ha='center', va='bottom')

    # 5. Time of day visualization
    ax5 = fig.add_subplot(gs[1, 3])
    df['day_of_submission'] = df['timestamp'].dt.day
    df['puzzle_day'] = df['timestamp'].dt.day
    df_same_day = df[df['day_of_submission'] == df['puzzle_day']]
    df_filtered = df_same_day[df_same_day['timestamp'].dt.hour >= 5]

    df_filtered['hour'] = df_filtered['timestamp'].dt.hour
    df_filtered['name'] = pd.Categorical(df_filtered['name'], categories=ordered_names, ordered=True)

    sns.violinplot(x='hour', y='name', data=df_filtered, inner='point', linewidth=1)
    plt.title('Time of Day (Release Day Only)', loc='left')
    plt.xlabel('Hour (UTC)')
    plt.ylabel('Participant')
    plt.xlim(4.5, 24)

    # Adjust layout
    plt.tight_layout()

    # Connect hover event
    fig.canvas.mpl_connect("motion_notify_event", hover)

    return fig


def main():
    parser = argparse.ArgumentParser(description='Visualize Advent of Code leaderboard')
    parser.add_argument('--anon', action='store_true',
                      help='anonymise usernames in visualization')
    parser.add_argument('--data', type=str, default='leaderboard.json',
                      help='path to leaderboard data file')
    args = parser.parse_args()

    fname = args.data
    if not os.path.exists(fname):
        print(f"Leaderboard data not found. \nPlease ensure you have a '{fname}' file in the current directory, downloaded from https://adventofcode.com/2024/leaderboard/private.")
        return
    with open(fname, 'r') as f:
        data = json.load(f)

    df = parse_completion_data(data, anonymise=args.anon)
    fig = create_visualizations(df)

    print("\nLeaderboard Statistics:")
    print(f"Active Participants: {len(df['name'].unique())}")
    print(f"Total Stars Collected: {len(df)}")
    print("\nTop 5 by Local Score:")
    top_scores = df.groupby('name')['local_score'].first().sort_values(ascending=False).head()
    for name, score in top_scores.items():
        print(f"{name}: {score}")

    plt.show()

if __name__ == "__main__":
    main()