from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class HotelBooking(models.Model):
    _name = 'hotel.booking'
    _description = 'Room Booking'
    _order = 'check_in_date desc'

    booking_code = fields.Char(string='Booking Code', readonly=True)
    room_id = fields.Many2one('hotel.room', string='Room', required=True)
    hotel_id = fields.Many2one('hotel.hotel', related='room_id.hotel_id', store=True)
    booking_date = fields.Date(string='Booking Date', default=fields.Date.context_today)
    check_in_date = fields.Date(string='Check-in Date', required=True)
    check_out_date = fields.Date(string='Check-out Date', required=True)
    create_uid = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    guest_name = fields.Char(string='Guest Name', required=True)
    guest_contact = fields.Char(string='Guest Contact')
    booking_status = fields.Selection([
        ('draft', 'Draft'),
        ('new', 'New'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled')
    ], string='Booking Status', default='new')
    total_nights = fields.Integer(string='Total Nights', compute='_compute_total_nights', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)

    @api.model
    def _auto_cancel_draft_bookings(self):
        draft_bookings = self.search([
            ('booking_status', '=', 'draft'),
            ('create_date', '<', fields.Datetime.now() - timedelta(hours=24))
        ])
        draft_bookings.write({'booking_status': 'cancelled'})

    def unlink(self):
        if not self.env.user.has_group('hotel.group_hotel_manager'):
            raise ValidationError('Only managers can delete bookings.')
        return super(HotelBooking, self).unlink()

    @api.model
    def create(self, vals):
        if 'booking_code' not in vals or not vals['booking_code']:
            sequence_code = self.env['ir.sequence'].next_by_code('hotel.booking')
            vals['booking_code'] = sequence_code or '/'
        return super(HotelBooking, self).create(vals)

    @api.depends('check_in_date', 'check_out_date')
    def _compute_total_nights(self):
        for booking in self:
            if booking.check_in_date and booking.check_out_date:
                delta = booking.check_out_date - booking.check_in_date
                booking.total_nights = delta.days
            else:
                booking.total_nights = 0

    @api.depends('total_nights', 'room_id.room_price')
    def _compute_total_amount(self):
        for booking in self:
            booking.total_amount = booking.total_nights * booking.room_id.room_price

    @api.constrains('check_in_date', 'check_out_date')
    def _check_dates(self):
        for booking in self:
            if booking.check_in_date and booking.check_out_date:
                if booking.check_in_date >= booking.check_out_date:
                    raise ValidationError('Check-out date must be after check-in date')

    @api.constrains('room_id', 'check_in_date', 'check_out_date')
    def _check_room_availability(self):
        for booking in self:
            overlapping_bookings = self.search([
                ('room_id', '=', booking.room_id.id),
                ('id', '!=', booking.id),
                ('check_in_date', '<', booking.check_out_date),
                ('check_out_date', '>', booking.check_in_date),
                ('booking_status', 'in', ['new', 'confirmed', 'checked_in'])
            ])
            if overlapping_bookings:
                raise ValidationError('The selected room is already booked for the given dates.')

    def action_confirm(self):
        self.write({'booking_status': 'confirmed'})
        self._send_status_update_email()

    def action_check_in(self):
        self.write({'booking_status': 'checked_in'})
        self.room_id.write({'room_status': 'occupied', 'last_rented_date': fields.Date.context_today(self)})
        self._send_status_update_email()

    def action_check_out(self):
        self.write({'booking_status': 'checked_out'})
        self.room_id.write({'room_status': 'available'})
        self._send_status_update_email()

    def _send_status_update_email(self):
        # Lấy người quản lý của khách sạn
        manager = self.hotel_id.manager_id
        if manager and manager.user_id:
            template = self.env.ref('hotel.booking_status_update_email_template')
            self.env['mail.template'].browse(template.id).send_mail(self.id, force_send=True)

    @api.model
    def _send_status_update_notification(self, booking):
        message = f"Booking {booking.booking_code} status updated to {booking.booking_status}."
        booking.message_post(body=message)

    def action_booking_approve(self):
        for record in self:
            record.write({'booking_status': 'confirmed'})
        # if record.booking_status == 'new':
        # else:
        #     raise ValidationError("Only bookings in 'New' status can be approved.")
