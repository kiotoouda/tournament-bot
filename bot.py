import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import json
from config import BOT_TOKEN, ADMIN_IDS, ALLOWED_TEAM_SIZES
from database import Database

# Initialize database
db = Database()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Registration states
TEAM_NAME, TEAM_LEADER, TEAM_ROSTER, TEAM_PHOTOS = range(4)

class TournamentBot:
    def __init__(self):
        self.user_data = {}
        self.registration_data = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        keyboard = []
        
        if user_id in ADMIN_IDS:
            keyboard = [
                [InlineKeyboardButton("🏆 Create Tournament", callback_data="create_tournament")],
                [InlineKeyboardButton("📊 Admin Panel", callback_data="admin_panel")],
                [InlineKeyboardButton("🎯 View Tournaments", callback_data="view_tournaments")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("🎯 View Tournaments", callback_data="view_tournaments")],
                [InlineKeyboardButton("📋 My Teams", callback_data="my_teams")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🤖 Welcome to Tournament Bot!\n\n"
            "Use this bot to register for tournaments and manage your teams.",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "create_tournament":
            await self.create_tournament_start(query, context)
        elif data == "admin_panel":
            await self.admin_panel(query, context)
        elif data == "view_tournaments":
            await self.view_tournaments(query, context)
        elif data.startswith("tournament_"):
            tournament_id = int(data.split("_")[1])
            await self.tournament_details(query, context, tournament_id)
        elif data.startswith("register_"):
            tournament_id = int(data.split("_")[1])
            await self.start_registration(query, context, tournament_id)
        elif data.startswith("view_team_"):
            team_id = int(data.split("_")[2])
            await self.show_team_details(query, context, team_id)
        elif data.startswith("delete_tournament_"):
            tournament_id = int(data.split("_")[2])
            await self.delete_tournament(query, context, tournament_id)
        elif data.startswith("delete_team_"):
            team_id = int(data.split("_")[2])
            await self.delete_team(query, context, team_id)
        elif data.startswith("start_bracket_"):
            tournament_id = int(data.split("_")[2])
            await self.start_bracket(query, context, tournament_id)
        elif data.startswith("match_"):
            match_data = data.split("_")
            match_id = int(match_data[1])
            team_id = int(match_data[2])
            await self.set_match_winner(query, context, match_id, team_id)

    async def create_tournament_start(self, query, context):
        if query.from_user.id not in ADMIN_IDS:
            await query.message.reply_text("❌ Only admins can create tournaments.")
            return
        
        context.user_data['creating_tournament'] = True
        await query.message.reply_text("🏆 Let's create a tournament!\n\nPlease enter the tournament name:")

    async def handle_tournament_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get('creating_tournament'):
            return
        
        tournament_name = update.message.text
        context.user_data['tournament_name'] = tournament_name
        
        keyboard = []
        for size in [8, 16, 32, 64]:
            keyboard.append([InlineKeyboardButton(f"{size} Teams", callback_data=f"size_{size}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🎯 Tournament: {tournament_name}\n\nSelect the number of teams:",
            reply_markup=reply_markup
        )

    async def handle_tournament_size(self, query, context):
        size = int(query.data.split("_")[1])
        tournament_name = context.user_data.get('tournament_name')
        
        tournament_id = db.create_tournament(tournament_name, size)
        
        # Notify all admins
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🏆 New Tournament Created!\n\n"
                    f"Name: {tournament_name}\n"
                    f"Size: {size} teams\n"
                    f"ID: {tournament_id}"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        await query.message.reply_text(
            f"✅ Tournament '{tournament_name}' created successfully!\n"
            f"Max teams: {size}\n\n"
            f"Players can now register using the 'View Tournaments' option."
        )
        
        # Clear creation state
        context.user_data.pop('creating_tournament', None)
        context.user_data.pop('tournament_name', None)

    async def admin_panel(self, query, context):
        if query.from_user.id not in ADMIN_IDS:
            await query.message.reply_text("❌ Only admins can access this panel.")
            return
        
        tournaments = db.get_active_tournaments()
        
        if not tournaments:
            await query.message.reply_text("📊 Admin Panel\n\nNo active tournaments.")
            return
        
        text = "📊 Admin Panel\n\nActive Tournaments:\n"
        keyboard = []
        
        for tournament in tournaments:
            text += f"\n🏆 {tournament[1]} (ID: {tournament[0]})\n"
            text += f"   Teams: {tournament[3]}/{tournament[2]}\n"
            text += f"   Status: {tournament[4]}\n"
            
            keyboard.append([
                InlineKeyboardButton(f"Manage {tournament[1]}", callback_data=f"tournament_{tournament[0]}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text, reply_markup=reply_markup)

    async def view_tournaments(self, query, context):
        tournaments = db.get_active_tournaments()
        
        if not tournaments:
            await query.message.reply_text("🎯 No active tournaments available for registration.")
            return
        
        text = "🎯 Active Tournaments:\n\n"
        keyboard = []
        
        for tournament in tournaments:
            text += f"🏆 {tournament[1]}\n"
            text += f"📊 {tournament[3]}/{tournament[2]} teams registered\n"
            text += f"🆔 ID: {tournament[0]}\n\n"
            
            if tournament[3] < tournament[2]:  # If not full
                keyboard.append([
                    InlineKeyboardButton(f"Register for {tournament[1]}", callback_data=f"register_{tournament[0]}")
                ])
            keyboard.append([
                InlineKeyboardButton(f"View Teams in {tournament[1]}", callback_data=f"tournament_{tournament[0]}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text, reply_markup=reply_markup)

    async def tournament_details(self, query, context, tournament_id):
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            await query.message.reply_text("❌ Tournament not found.")
            return
        
        teams = db.get_tournament_teams(tournament_id)
        user_id = query.from_user.id
        
        text = f"🏆 {tournament[1]}\n"
        text += f"📊 Teams: {tournament[3]}/{tournament[2]}\n"
        text += f"📝 Status: {tournament[4]}\n\n"
        text += "Registered Teams:\n"
        
        keyboard = []
        
        for team in teams:
            text += f"• {team[2]} (Leader: @{team[3]})\n"
            keyboard.append([
                InlineKeyboardButton(f"View {team[2]}", callback_data=f"view_team_{team[0]}")
            ])
        
        # Admin controls
        if user_id in ADMIN_IDS:
            if tournament[4] == "registration" and tournament[3] == tournament[2]:
                keyboard.append([
                    InlineKeyboardButton("🚀 Start Bracket", callback_data=f"start_bracket_{tournament_id}")
                ])
            keyboard.append([
                InlineKeyboardButton("🗑 Delete Tournament", callback_data=f"delete_tournament_{tournament_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text, reply_markup=reply_markup)

    async def start_registration(self, query, context, tournament_id):
        tournament = db.get_tournament(tournament_id)
        if not tournament:
            await query.message.reply_text("❌ Tournament not found.")
            return
        
        if tournament[3] >= tournament[2]:
            await query.message.reply_text("❌ Tournament is full. Registration closed.")
            return
        
        self.registration_data[query.from_user.id] = {
            'tournament_id': tournament_id,
            'step': TEAM_NAME
        }
        
        await query.message.reply_text(
            f"🎯 Registration for {tournament[1]}\n\n"
            "Step 1/4: Please enter your team name:"
        )

    async def handle_team_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.registration_data:
            return
        
        team_name = update.message.text
        self.registration_data[user_id]['team_name'] = team_name
        self.registration_data[user_id]['step'] = TEAM_LEADER
        
        await update.message.reply_text(
            "✅ Team name saved!\n\n"
            "Step 2/4: Please enter team leader's username (without @):"
        )

    async def handle_team_leader(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.registration_data:
            return
        
        leader_username = update.message.text
        self.registration_data[user_id]['leader_username'] = leader_username
        self.registration_data[user_id]['step'] = TEAM_ROSTER
        self.registration_data[user_id]['roster'] = []
        
        await update.message.reply_text(
            "✅ Leader username saved!\n\n"
            "Step 3/4: Please enter team roster (3-4 usernames, one per line):\n"
            "Example:\n"
            "player1\n"
            "player2\n"
            "player3"
        )

    async def handle_team_roster(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.registration_data:
            return
        
        roster_text = update.message.text
        roster = [line.strip() for line in roster_text.split('\n') if line.strip()]
        
        if len(roster) not in ALLOWED_TEAM_SIZES:
            await update.message.reply_text(
                f"❌ Team size must be {ALLOWED_TEAM_SIZES}. Please enter exactly {ALLOWED_TEAM_SIZES} usernames:"
            )
            return
        
        self.registration_data[user_id]['roster'] = roster
        self.registration_data[user_id]['step'] = TEAM_PHOTOS
        self.registration_data[user_id]['photos'] = []
        
        await update.message.reply_text(
            "✅ Roster saved!\n\n"
            "Step 4/4: Please send 3-4 photos of your team (send them one by one):"
        )

    async def handle_team_photos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.registration_data or self.registration_data[user_id]['step'] != TEAM_PHOTOS:
            return
        
        if not update.message.photo:
            await update.message.reply_text("❌ Please send photos only.")
            return
        
        photo_file_id = update.message.photo[-1].file_id
        self.registration_data[user_id]['photos'].append(photo_file_id)
        
        current_count = len(self.registration_data[user_id]['photos'])
        remaining = 4 - current_count
        
        if remaining > 0:
            await update.message.reply_text(f"✅ Photo {current_count}/4 received. Send {remaining} more photos.")
        else:
            # Registration complete
            data = self.registration_data[user_id]
            success, message, is_full = db.register_team(
                data['tournament_id'],
                data['team_name'],
                data['leader_username'],
                data['roster'],
                data['photos']
            )
            
            if success:
                tournament = db.get_tournament(data['tournament_id'])
                
                # Notify admins
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"🎉 New Team Registered!\n\n"
                            f"🏆 Tournament: {tournament[1]}\n"
                            f"👥 Team: {data['team_name']}\n"
                            f"👑 Leader: @{data['leader_username']}\n"
                            f"📊 Roster: {', '.join(data['roster'])}\n"
                            f"📈 Progress: {tournament[3]}/{tournament[2]} teams"
                        )
                        
                        # Send photos to admin
                        media_group = [InputMediaPhoto(photo) for photo in data['photos'][:2]]  # Send first 2 photos
                        await context.bot.send_media_group(admin_id, media_group)
                        
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_id}: {e}")
                
                await update.message.reply_text(
                    f"✅ Registration successful!\n\n"
                    f"Team: {data['team_name']}\n"
                    f"Leader: @{data['leader_username']}\n"
                    f"Roster: {', '.join(data['roster'])}\n\n"
                    f"You are now registered for the tournament!"
                )
                
                if is_full:
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                admin_id,
                                f"🎊 Tournament '{tournament[1]}' is now FULL!\n"
                                f"All {tournament[2]} teams have registered.\n"
                                f"Use the admin panel to start the bracket."
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify admin {admin_id}: {e}")
            else:
                await update.message.reply_text(f"❌ Registration failed: {message}")
            
            # Clear registration data
            self.registration_data.pop(user_id, None)

    async def show_team_details(self, query, context, team_id):
        team = db.get_team_details(team_id)
        if not team:
            await query.message.reply_text("❌ Team not found.")
            return
        
        roster = json.loads(team[4])
        photos = json.loads(team[5])
        
        text = f"👥 Team Details\n\n"
        text += f"🏷 Name: {team[2]}\n"
        text += f"👑 Leader: @{team[3]}\n"
        text += f"📊 Roster:\n"
        for player in roster:
            text += f"  • {player}\n"
        text += f"📅 Registered: {team[6]}"
        
        # Send team info
        await query.message.reply_text(text)
        
        # Send team photos
        if photos:
            media_group = [InputMediaPhoto(photo) for photo in photos[:4]]
            await context.bot.send_media_group(query.message.chat_id, media_group)

    async def delete_tournament(self, query, context, tournament_id):
        if query.from_user.id not in ADMIN_IDS:
            await query.message.reply_text("❌ Only admins can delete tournaments.")
            return
        
        db.delete_tournament(tournament_id)
        await query.message.reply_text("✅ Tournament deleted successfully.")

    async def delete_team(self, query, context, team_id):
        if query.from_user.id not in ADMIN_IDS:
            await query.message.reply_text("❌ Only admins can delete teams.")
            return
        
        db.delete_team(team_id)
        await query.message.reply_text("✅ Team deleted successfully.")

    async def start_bracket(self, query, context, tournament_id):
        if query.from_user.id not in ADMIN_IDS:
            await query.message.reply_text("❌ Only admins can start brackets.")
            return
        
        db.create_bracket(tournament_id)
        await self.show_current_matches(query, context, tournament_id)

    async def show_current_matches(self, query, context, tournament_id, round_number=1):
        matches = db.get_current_matches(tournament_id, round_number)
        
        if not matches:
            await query.message.reply_text("No current matches available.")
            return
        
        text = f"🎯 Round {round_number} Matches\n\n"
        keyboard = []
        
        for match in matches:
            team_a = db.get_team_details(match[4])
            team_b = db.get_team_details(match[5])
            
            text += f"Match {match[3]}:\n"
            text += f"  {team_a[2]} vs {team_b[2]}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"🏆 {team_a[2]} wins", callback_data=f"match_{match[0]}_{team_a[0]}"),
                InlineKeyboardButton(f"🏆 {team_b[2]} wins", callback_data=f"match_{match[0]}_{team_b[0]}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(text, reply_markup=reply_markup)

    async def set_match_winner(self, query, context, match_id, winner_id):
        if query.from_user.id not in ADMIN_IDS:
            await query.message.reply_text("❌ Only admins can set match winners.")
            return
        
        db.set_match_winner(match_id, winner_id)
        
        # Get match details to find tournament and round
        # This would need additional database methods to properly handle bracket progression
        
        await query.message.reply_text("✅ Match result recorded!")

def main():
    bot = TournamentBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start the bot
    application.run_polling()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot = TournamentBot()
    
    if user_id in bot.registration_data:
        step = bot.registration_data[user_id]['step']
        
        if step == TEAM_NAME:
            await bot.handle_team_name(update, context)
        elif step == TEAM_LEADER:
            await bot.handle_team_leader(update, context)
        elif step == TEAM_ROSTER:
            await bot.handle_team_roster(update, context)
    elif context.user_data.get('creating_tournament'):
        await bot.handle_tournament_name(update, context)

if __name__ == '__main__':
    main()
