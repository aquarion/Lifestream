
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "achievements"(
  "ID" TEXT,
  "AchievementCategory" TEXT,
  "Name" TEXT,
  "Description" TEXT,
  "AchievementTarget" TEXT,
  "byte_0" TEXT,
  "Points" TEXT,
  "Title" TEXT,
  "Item" TEXT,
  "byte_1" TEXT,
  "byte_2" TEXT,
  "byte_3" TEXT,
  "Icon" TEXT,
  "byte_4" TEXT,
  "Type" TEXT,
  "Key" TEXT,
  "Data_0" TEXT,
  "Data_1" TEXT,
  "Data_2" TEXT,
  "Data_3" TEXT,
  "Data_4" TEXT,
  "Data_5" TEXT,
  "Data_6" TEXT,
  "Data_7" TEXT,
  "Order" TEXT,
  "byte_5" TEXT,
  "AchievementHideCondition" TEXT
);
COMMIT;