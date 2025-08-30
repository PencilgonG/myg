/*
  Warnings:

  - You are about to drop the column `elo` on the `UserProfile` table. All the data in the column will be lost.

*/
-- CreateEnum
CREATE TYPE "LoLRegion" AS ENUM ('EUW', 'EUNE', 'NA', 'KR', 'JP', 'OCE', 'BR', 'LAN', 'LAS', 'TR', 'RU');

-- AlterTable
ALTER TABLE "UserProfile" DROP COLUMN "elo",
ADD COLUMN     "region" "LoLRegion";
