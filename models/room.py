from odoo import models, fields, api
from datetime import timedelta

class HotelRoom(models.Model):
    _name = 'hotel.room'
    _description = 'Hotel Room'

    room_code = fields.Char(string='Room Code', required=True)
    hotel_id = fields.Many2one('hotel.hotel', string='Hotel', required=True)
    bed_type = fields.Selection([
        ('single', 'Single'),
        ('double', 'Double'),
        ('suite', 'Suite')
    ], string='Bed Type', required=True)
    room_price = fields.Float(string='Price per Night', required=True)
    feature_ids = fields.Many2many('hotel.feature', string='Features')
    room_status = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance')
    ], string='Status', default='available', tracking=True)
    booking_ids = fields.One2many('hotel.booking', 'room_id', string='Bookings')
    room_active = fields.Boolean(default=True)
    last_rented_date = fields.Date(string='Last Rented Date', readonly=True)

    _sql_constraints = [
        ('unique_room_code_hotel', 'UNIQUE(room_code, hotel_id)', 'Room code must be unique per hotel!')
    ]

    @api.model
    def _check_unrented_rooms_and_apply_discount(self):
        one_week_ago = fields.Date.context_today(self) - timedelta(days=7)
        unrented_rooms = self.search([
            ('last_rented_date', '<', one_week_ago),
            ('room_status', '=', 'available')
        ])
        for room in unrented_rooms:
            room.room_price *= 0.9  # Apply a 10% discount
            room.message_post(body="Room price reduced by 10% due to being unrented for a week.")