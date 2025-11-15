import pandas as pd

# Load both files
main_df = pd.read_csv("texas_rent_market_data.csv")
update_df = pd.read_csv("texas_zipcode_list.csv")

# Merge on ZipCode
merged_df = pd.merge(main_df, update_df, on="ZipCode", how="left", suffixes=("", "_update"))

# Update the columns
merged_df["City"] = merged_df["City"].combine_first(merged_df["City_update"])
merged_df["County"] = merged_df["County"].combine_first(merged_df["County_update"])
merged_df["State"] = merged_df["State"].combine_first(merged_df["State_update"])

# Drop the extra columns
merged_df = merged_df.drop(columns=["City_update"])
merged_df = merged_df.drop(columns=["County_update"])
merged_df = merged_df.drop(columns=["State_update"])

# Save back to CSV
merged_df.to_csv("market_data_updated.csv", index=False)

print("Updated CSV saved as market_data_updated.csv")