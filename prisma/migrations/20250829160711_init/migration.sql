-- CreateEnum
CREATE TYPE "GameMode" AS ENUM ('SR_5v5', 'SR_4v4', 'SR_3v3', 'SR_2v2');

-- CreateEnum
CREATE TYPE "LobbyState" AS ENUM ('CREATED', 'RUNNING', 'FINISHED');

-- CreateEnum
CREATE TYPE "MatchState" AS ENUM ('PENDING', 'DONE');

-- CreateEnum
CREATE TYPE "RoleName" AS ENUM ('TOP', 'JUNGLE', 'MID', 'ADC', 'SUPPORT', 'FLEX');

-- CreateTable
CREATE TABLE "Lobby" (
    "id" TEXT NOT NULL,
    "guildId" TEXT NOT NULL,
    "channelId" TEXT NOT NULL,
    "messageId" TEXT,
    "name" TEXT NOT NULL,
    "slots" INTEGER NOT NULL,
    "mode" "GameMode" NOT NULL,
    "state" "LobbyState" NOT NULL DEFAULT 'CREATED',
    "createdBy" TEXT NOT NULL,
    "currentRound" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Lobby_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Team" (
    "id" TEXT NOT NULL,
    "lobbyId" TEXT NOT NULL,
    "number" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "roleId" TEXT,
    "textChannelId" TEXT,
    "voiceChannelId" TEXT,

    CONSTRAINT "Team_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Match" (
    "id" TEXT NOT NULL,
    "lobbyId" TEXT NOT NULL,
    "round" INTEGER NOT NULL,
    "indexInRound" INTEGER NOT NULL,
    "blueTeamId" TEXT NOT NULL,
    "redTeamId" TEXT NOT NULL,
    "draftBlueUrl" TEXT,
    "draftRedUrl" TEXT,
    "specUrl" TEXT,
    "state" "MatchState" NOT NULL DEFAULT 'PENDING',
    "winnerTeamId" TEXT,

    CONSTRAINT "Match_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UserProfile" (
    "id" TEXT NOT NULL,
    "discordUserId" TEXT NOT NULL,
    "summonerName" TEXT,
    "preferredRoles" "RoleName"[] DEFAULT ARRAY[]::"RoleName"[],
    "opggUrl" TEXT,
    "dpmUrl" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "UserProfile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "LobbyParticipant" (
    "id" TEXT NOT NULL,
    "lobbyId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "isCaptain" BOOLEAN NOT NULL DEFAULT false,
    "isSub" BOOLEAN NOT NULL DEFAULT false,
    "selectedRole" "RoleName",
    "teamNumber" INTEGER,

    CONSTRAINT "LobbyParticipant_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "PlayerStats" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "dpmAvg" DOUBLE PRECISION,
    "csmAvg" DOUBLE PRECISION,
    "kdaAvg" DOUBLE PRECISION,

    CONSTRAINT "PlayerStats_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Team_lobbyId_number_key" ON "Team"("lobbyId", "number");

-- CreateIndex
CREATE UNIQUE INDEX "UserProfile_discordUserId_key" ON "UserProfile"("discordUserId");

-- CreateIndex
CREATE UNIQUE INDEX "LobbyParticipant_lobbyId_userId_key" ON "LobbyParticipant"("lobbyId", "userId");

-- CreateIndex
CREATE UNIQUE INDEX "PlayerStats_userId_key" ON "PlayerStats"("userId");

-- AddForeignKey
ALTER TABLE "Team" ADD CONSTRAINT "Team_lobbyId_fkey" FOREIGN KEY ("lobbyId") REFERENCES "Lobby"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Match" ADD CONSTRAINT "Match_lobbyId_fkey" FOREIGN KEY ("lobbyId") REFERENCES "Lobby"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Match" ADD CONSTRAINT "Match_blueTeamId_fkey" FOREIGN KEY ("blueTeamId") REFERENCES "Team"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Match" ADD CONSTRAINT "Match_redTeamId_fkey" FOREIGN KEY ("redTeamId") REFERENCES "Team"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "LobbyParticipant" ADD CONSTRAINT "LobbyParticipant_lobbyId_fkey" FOREIGN KEY ("lobbyId") REFERENCES "Lobby"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "LobbyParticipant" ADD CONSTRAINT "LobbyParticipant_userId_fkey" FOREIGN KEY ("userId") REFERENCES "UserProfile"("discordUserId") ON DELETE NO ACTION ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "PlayerStats" ADD CONSTRAINT "PlayerStats_userId_fkey" FOREIGN KEY ("userId") REFERENCES "UserProfile"("discordUserId") ON DELETE RESTRICT ON UPDATE CASCADE;
