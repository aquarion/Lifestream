BEGIN TRANSACTION;

CREATE TABLE
  IF NOT EXISTS "achievements" (
    "ID" TEXT,
    "Name" TEXT,
    "Description" TEXT,
    "Item" TEXT,
    "Icon" TEXT,
    "Key" TEXT,
    "Data_0" TEXT,
    "Data_1" TEXT,
    "Data_2" TEXT,
    "Data_3" TEXT,
    "Data_4" TEXT,
    "Data_5" TEXT,
    "Data_6" TEXT,
    "Data_7" TEXT,
    "Title" TEXT,
    "Order" TEXT,
    "AchievementCategory" TEXT,
    "AchievementTarget" TEXT,
    "Unknown0" TEXT,
    "Points" TEXT,
    "Unknown1" TEXT,
    "Unknown2" TEXT,
    "Unknown3" TEXT,
    "Unknown4" TEXT,
    "Type" TEXT,
    "Unknown5" TEXT,
    "AchievementHideCondition" TEXT
  );

COMMIT;