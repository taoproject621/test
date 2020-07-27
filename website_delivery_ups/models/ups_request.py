# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import io
from PIL import Image
import logging
import os
import re

from zeep import Client, Plugin
from zeep.exceptions import Fault

from odoo import _, _lt

_logger = logging.getLogger(__name__)
# uncomment to enable logging of SOAP requests and responses
# logging.getLogger('zeep.transports').setLevel(logging.DEBUG)

TNT_SERVICE_TYPE = {
    '03': 'GND',
    '01': '1DM',
    '14': '1DA',
    '13': '1DP',
    '02': '2DM',
    '59': '2DA',
    '12': '3DS'
}

UPS_ERROR_MAP = {
    '110002': _lt("Please provide at least one item to ship."),
    '110208': _lt("Please set a valid country in the recipient address."),
    '110308': _lt("Please set a valid country in the warehouse address."),
    '110548': _lt(
        "A shipment cannot have a KGS/IN or LBS/CM as its unit of measurements. Configure it from the delivery method."),
    '111057': _lt(
        "This measurement system is not valid for the selected country. Please switch from LBS/IN to KGS/CM (or vice versa). Configure it from the delivery method."),
    '111091': _lt(
        "The selected service is not possible from your warehouse to the recipient address, please choose another service."),
    '111100': _lt("The selected service is invalid from the requested warehouse, please choose another service."),
    '111107': _lt("Please provide a valid zip code in the warehouse address."),
    '111210': _lt("The selected service is invalid to the recipient address, please choose another service."),
    '111212': _lt("Please provide a valid package type available for service and selected locations."),
    '111500': _lt("The selected service is not valid with the selected packaging."),
    '112111': _lt("Please provide a valid shipper number/Carrier Account."),
    '113020': _lt("Please provide a valid zip code in the warehouse address."),
    '113021': _lt("Please provide a valid zip code in the recipient address."),
    '120031': _lt("Exceeds Total Number of allowed pieces per World Wide Express Shipment."),
    '120100': _lt("Please provide a valid shipper number/Carrier Account."),
    '120102': _lt("Please provide a valid street in shipper's address."),
    '120105': _lt("Please provide a valid city in the shipper's address."),
    '120106': _lt("Please provide a valid state in the shipper's address."),
    '120107': _lt("Please provide a valid zip code in the shipper's address."),
    '120108': _lt("Please provide a valid country in the shipper's address."),
    '120109': _lt("Please provide a valid shipper phone number."),
    '120113': _lt("Shipper number must contain alphanumeric characters only."),
    '120114': _lt("Shipper phone extension cannot exceed the length of 4."),
    '120115': _lt("Shipper Phone must be at least 10 alphanumeric characters."),
    '120116': _lt("Shipper phone extension must contain only numbers."),
    '120122': _lt("Please provide a valid shipper Number/Carrier Account."),
    '120124': _lt("The requested service is unavailable between the selected locations."),
    '120202': _lt("Please provide a valid street in the recipient address."),
    '120205': _lt("Please provide a valid city in the recipient address."),
    '120206': _lt("Please provide a valid state in the recipient address."),
    '120207': _lt("Please provide a valid zipcode in the recipient address."),
    '120208': _lt("Please provide a valid Country in recipient's address."),
    '120209': _lt("Please provide a valid phone number for the recipient."),
    '120212': _lt("Recipient PhoneExtension cannot exceed the length of 4."),
    '120213': _lt("Recipient Phone must be at least 10 alphanumeric characters."),
    '120214': _lt("Recipient PhoneExtension must contain only numbers."),
    '120302': _lt("Please provide a valid street in the warehouse address."),
    '120305': _lt("Please provide a valid City in the warehouse address."),
    '120306': _lt("Please provide a valid State in the warehouse address."),
    '120307': _lt("Please provide a valid Zip in the warehouse address."),
    '120308': _lt("Please provide a valid Country in the warehouse address."),
    '120309': _lt("Please provide a valid warehouse Phone Number"),
    '120312': _lt("Warehouse PhoneExtension cannot exceed the length of 4."),
    '120313': _lt("Warehouse Phone must be at least 10 alphanumeric characters."),
    '120314': _lt("Warehouse Phone must contain only numbers."),
    '120412': _lt("Please provide a valid shipper Number/Carrier Account."),
    '121057': _lt(
        "This measurement system is not valid for the selected country. Please switch from LBS/IN to KGS/CM (or vice versa). Configure it from delivery method"),
    '121210': _lt("The requested service is unavailable between the selected locations."),
    '128089': _lt(
        "Access License number is Invalid. Provide a valid number (Length sholuld be 0-35 alphanumeric characters)"),
    '190001': _lt("Cancel shipment not available at this time , Please try again Later."),
    '190100': _lt("Provided Tracking Ref. Number is invalid."),
    '190109': _lt("Provided Tracking Ref. Number is invalid."),
    '250001': _lt("Access License number is invalid for this provider.Please re-license."),
    '250002': _lt("Username/Password is invalid for this delivery provider."),
    '250003': _lt("Access License number is invalid for this delivery provider."),
    '250004': _lt("Username/Password is invalid for this delivery provider."),
    '250006': _lt("The maximum number of user access attempts was exceeded. So please try again later"),
    '250007': _lt("The UserId is currently locked out; please try again in 24 hours."),
    '250009': _lt("Provided Access License Number not found in the UPS database"),
    '250038': _lt("Please provide a valid shipper number/Carrier Account."),
    '250047': _lt("Access License number is revoked contact UPS to get access."),
    '250052': _lt("Authorization system is currently unavailable , try again later."),
    '250053': _lt("UPS Server Not Found"),
    '9120200': _lt("Please provide at least one item to ship")
}


class Package():
    def __init__(self, carrier, weight, quant_pack=False, name=''):
        self.weight = carrier._ups_convert_weight(weight, carrier.ups_package_weight_unit)
        self.weight_unit = carrier.ups_package_weight_unit
        self.name = name
        self.dimension_unit = carrier.ups_package_dimension_unit
        if quant_pack:
            self.dimension = {'length': quant_pack.length, 'width': quant_pack.width, 'height': quant_pack.height}
        else:
            self.dimension = {'length': carrier.ups_default_packaging_id.length,
                              'width': carrier.ups_default_packaging_id.width,
                              'height': carrier.ups_default_packaging_id.height}
        self.packaging_type = quant_pack and quant_pack.shipper_package_code or False


class LogPlugin(Plugin):
    """ Small plugin for zeep that catches out/ingoing XML requests and logs them"""

    def __init__(self, debug_logger):
        self.debug_logger = debug_logger

    def egress(self, envelope, http_headers, operation, binding_options):
        self.debug_logger(envelope, 'ups_request')
        return envelope, http_headers

    def ingress(self, envelope, http_headers, operation):
        self.debug_logger(envelope, 'ups_response')
        return envelope, http_headers


class FixRequestNamespacePlug(Plugin):
    def __init__(self, root):
        self.root = root

    def marshalled(self, context):
        context.envelope = context.envelope.prune()


class UPSRequest():
    def __init__(self, debug_logger, username, password, shipper_number, access_number, prod_environment):
        self.debug_logger = debug_logger
        # Product and Testing url
        self.endurl = "https://onlinetools.ups.com/webservices/"
        if not prod_environment:
            self.endurl = "https://wwwcie.ups.com/webservices/"

        # Basic detail require to authenticate
        self.username = username
        self.password = password
        self.shipper_number = shipper_number
        self.access_number = access_number

        self.rate_wsdl = '../api/RateWS.wsdl'
        self.ns = {'err': "http://www.ups.com/XMLSchema/XOLTWS/Error/v1.1"}

    def _add_security_header(self, client, api):
        # set the detail which require to authenticate
        user_token = {'Username': self.username, 'Password': self.password}
        access_token = {'AccessLicenseNumber': self.access_number}
        security = client.get_element('ns0:UPSSecurity')(UsernameToken=user_token, ServiceAccessToken=access_token)
        security['location'] = '%s%s' % (self.endurl, api)
        client.set_default_soapheaders([security])

    def _set_client(self, wsdl, api, root):
        wsdl_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), wsdl)
        client = Client('file:///%s' % wsdl_path.lstrip('/'),
                        plugins=[FixRequestNamespacePlug(root), LogPlugin(self.debug_logger)])
        self.factory_ns2 = client.type_factory('ns2')
        self.factory_ns3 = client.type_factory('ns3')
        self._add_security_header(client, api)
        return client

    def _clean_phone_number(self, phone):
        return re.sub('[^0-9]', '', phone)

    def check_required_value(self, shipper, ship_from, ship_to, order=False, picking=False):
        required_field = {'city': 'City', 'zip': 'ZIP code', 'country_id': 'Country', 'phone': 'Phone'}
        # Check required field for shipper
        res = [required_field[field] for field in required_field if not shipper[field]]
        if shipper.country_id.code in ('US', 'CA', 'IE') and not shipper.state_id.code:
            res.append('State')
        if not shipper.street and not shipper.street2:
            res.append('Street')
        if res:
            return _("The address of your company is missing or wrong.\n(Missing field(s) : %s)") % ",".join(res)
        if len(self._clean_phone_number(shipper.phone)) < 10:
            return _(UPS_ERROR_MAP.get('120115'))
        # Check required field for warehouse address
        res = [required_field[field] for field in required_field if not ship_from[field]]
        if ship_from.country_id.code in ('US', 'CA', 'IE') and not ship_from.state_id.code:
            res.append('State')
        if not ship_from.street and not ship_from.street2:
            res.append('Street')
        if res:
            return _("The address of your warehouse is missing or wrong.\n(Missing field(s) : %s)") % ",".join(res)
        if len(self._clean_phone_number(ship_from.phone)) < 10:
            return _(UPS_ERROR_MAP.get('120313'))
        # Check required field for recipient address
        res = [required_field[field] for field in required_field if field != 'phone' and not ship_to[field]]
        if ship_to.country_id.code in ('US', 'CA', 'IE') and not ship_to.state_id.code:
            res.append('State')
        if not ship_to.street and not ship_to.street2:
            res.append('Street')
        if picking and not order:
            order = picking.sale_id
        phone = ship_to.mobile or ship_to.phone
        if order and not phone:
            phone = order.partner_id.mobile or order.partner_id.phone
        if order:
            if not order.order_line:
                return _("Please provide at least one item to ship.")

        if picking:

            packages_without_weight = picking.move_line_ids.mapped('result_package_id').filtered(
                lambda p: not p.shipping_weight)
            if packages_without_weight:
                return _('Packages %s do not have a positive shipping weight.') % (
                    ', '.join(packages_without_weight.mapped('display_name')))
        if not phone:
            res.append('Phone')
        if res:
            return _("The recipient address is missing or wrong.\n(Missing field(s) : %s)") % ",".join(res)
        if len(self._clean_phone_number(phone)) < 10:
            return _(UPS_ERROR_MAP.get('120213'))
        return False

    def get_error_message(self, error_code, description):
        result = {}
        result['error_message'] = UPS_ERROR_MAP.get(error_code)
        if not result['error_message']:
            result['error_message'] = description
        return result

    def save_label(self, image64, label_file_type='GIF'):
        img_decoded = base64.decodebytes(image64.encode('utf-8'))
        if label_file_type == 'GIF':
            # Label format is GIF, so need to rotate and convert as PDF
            image_string = io.BytesIO(img_decoded)
            im = Image.open(image_string)
            label_result = io.BytesIO()
            im.save(label_result, 'pdf')
            return label_result.getvalue()
        else:
            return img_decoded

    def set_package_detail(self, packages, packaging_type, ship_from, ship_to, cod_info, request_type):
        Packages = []
        if request_type == "rating":
            MeasurementType = self.factory_ns2.CodeDescriptionType
        elif request_type == "shipping":
            MeasurementType = self.factory_ns2.ShipUnitOfMeasurementType
        for i, p in enumerate(packages):
            package = self.factory_ns2.PackageType()
            if hasattr(package, 'Packaging'):
                package.Packaging = self.factory_ns2.PackagingType()
                package.Packaging.Code = p.packaging_type or packaging_type or ''
            elif hasattr(package, 'PackagingType'):
                package.PackagingType = self.factory_ns2.CodeDescriptionType()
                package.PackagingType.Code = p.packaging_type or packaging_type or ''

            if p.dimension_unit and any(p.dimension.values()):
                package.Dimensions = self.factory_ns2.DimensionsType()
                package.Dimensions.UnitOfMeasurement = MeasurementType()
                package.Dimensions.UnitOfMeasurement.Code = p.dimension_unit or ''
                package.Dimensions.Length = p.dimension['length'] or ''
                package.Dimensions.Width = p.dimension['width'] or ''
                package.Dimensions.Height = p.dimension['height'] or ''

            if cod_info:
                package.PackageServiceOptions = self.factory_ns2.PackageServiceOptionsType()
                package.PackageServiceOptions.COD = self.factory_ns2.CODType()
                package.PackageServiceOptions.COD.CODFundsCode = str(cod_info['funds_code'])
                package.PackageServiceOptions.COD.CODAmount = self.factory_ns2.CODAmountType()
                package.PackageServiceOptions.COD.CODAmount.MonetaryValue = cod_info['monetary_value']
                package.PackageServiceOptions.COD.CODAmount.CurrencyCode = cod_info['currency']

            package.PackageWeight = self.factory_ns2.PackageWeightType()
            package.PackageWeight.UnitOfMeasurement = MeasurementType()
            package.PackageWeight.UnitOfMeasurement.Code = p.weight_unit or ''
            package.PackageWeight.Weight = p.weight or ''

            # Package and shipment reference text is only allowed for shipments within
            # the USA and within Puerto Rico. This is a UPS limitation.
            if (p.name and ship_from.country_id.code in ('US') and ship_to.country_id.code in ('US')):
                reference_number = self.factory_ns2.ReferenceNumberType()
                reference_number.Code = 'PM'
                reference_number.Value = p.name
                reference_number.BarCodeIndicator = p.name
                package.ReferenceNumber = reference_number

            Packages.append(package)
        return Packages

    def get_shipping_price(self, shipment_info, packages, shipper, ship_from, ship_to, packaging_type, service_type,
                           saturday_delivery, cod_info):
        """
            Get Shipping Price
            :param shipment_info:
            :param packages:
            :param shipper:
            :param ship_from:
            :param ship_to:
            :param packaging_type:
            :param service_type:
            :param saturday_delivery:
            :param cod_info:
            :return:
        """
        client = self._set_client(self.rate_wsdl, 'Rate', 'RateRequest')
        request = self.factory_ns3.RequestType()
        request.RequestOption = 'Rate'

        classification = self.factory_ns2.CodeDescriptionType()
        classification.Code = '00'  # Get rates for the shipper account
        classification.Description = 'Get rates for the shipper account'

        request_type = "rating"
        shipment = self.factory_ns2.ShipmentType()

        for package in self.set_package_detail(packages, packaging_type, ship_from, ship_to, cod_info,
                                               request_type):
            shipment.Package.append(package)

        shipment.Shipper = self.factory_ns2.ShipperType()
        shipment.Shipper.Name = shipper.name or ''
        shipment.Shipper.Address = self.factory_ns2.AddressType()
        shipment.Shipper.Address.AddressLine = [shipper.street or '', shipper.street2 or '']
        shipment.Shipper.Address.City = shipper.city or ''
        shipment.Shipper.Address.PostalCode = shipper.zip or ''
        shipment.Shipper.Address.CountryCode = shipper.country_id.code or ''
        if shipper.country_id.code in ('US', 'CA', 'IE'):
            shipment.Shipper.Address.StateProvinceCode = shipper.state_id.code or ''
        shipment.Shipper.ShipperNumber = self.shipper_number or ''
        # shipment.Shipper.Phone.Number = shipper.phone or ''

        shipment.ShipFrom = self.factory_ns2.ShipFromType()
        shipment.ShipFrom.Name = ship_from.name or ''
        shipment.ShipFrom.Address = self.factory_ns2.AddressType()
        shipment.ShipFrom.Address.AddressLine = [ship_from.street or '', ship_from.street2 or '']
        shipment.ShipFrom.Address.City = ship_from.city or ''
        shipment.ShipFrom.Address.PostalCode = ship_from.zip or ''
        shipment.ShipFrom.Address.CountryCode = ship_from.country_id.code or ''
        if ship_from.country_id.code in ('US', 'CA', 'IE'):
            shipment.ShipFrom.Address.StateProvinceCode = ship_from.state_id.code or ''
        # shipment.ShipFrom.Phone.Number = ship_from.phone or ''

        shipment.ShipTo = self.factory_ns2.ShipToType()
        shipment.ShipTo.Name = ship_to.name or ''
        shipment.ShipTo.Address = self.factory_ns2.AddressType()
        shipment.ShipTo.Address.AddressLine = [ship_to.street or '', ship_to.street2 or '']
        shipment.ShipTo.Address.City = ship_to.city or ''
        shipment.ShipTo.Address.PostalCode = ship_to.zip or ''
        shipment.ShipTo.Address.CountryCode = ship_to.country_id.code or ''
        if ship_to.country_id.code in ('US', 'CA', 'IE'):
            shipment.ShipTo.Address.StateProvinceCode = ship_to.state_id.code or ''
        # shipment.ShipTo.Phone.Number = ship_to.phone or ''
        if not ship_to.commercial_partner_id.is_company:
            shipment.ShipTo.Address.ResidentialAddressIndicator = None

        shipment.Service = self.factory_ns2.CodeDescriptionType()
        shipment.Service.Code = service_type or ''
        shipment.Service.Description = 'Service Code'
        if service_type == "96":
            shipment.NumOfPieces = int(shipment_info.get('total_qty'))

        if saturday_delivery:
            shipment.ShipmentServiceOptions = self.factory_ns2.ShipmentServiceOptionsType()
            shipment.ShipmentServiceOptions.SaturdayDeliveryIndicator = saturday_delivery
        else:
            shipment.ShipmentServiceOptions = ''

        shipment.ShipmentRatingOptions = self.factory_ns2.ShipmentRatingOptionsType()
        shipment.ShipmentRatingOptions.NegotiatedRatesIndicator = 1

        try:
            # Get rate using for provided detail
            response = client.service.ProcessRate(Request=request, CustomerClassification=classification,
                                                  Shipment=shipment)

            # Check if ProcessRate is not success then return reason for that
            if response.Response.ResponseStatus.Code != "1":
                return self.get_error_message(response.Response.ResponseStatus.Code,
                                              response.Response.ResponseStatus.Description)

            result = {}
            result['currency_code'] = response.RatedShipment[0].TotalCharges.CurrencyCode

            # Some users are qualified to receive negotiated rates
            negotiated_rate = 'NegotiatedRateCharges' in response.RatedShipment[0] and response.RatedShipment[
                0].NegotiatedRateCharges and response.RatedShipment[
                                  0].NegotiatedRateCharges.TotalCharge.MonetaryValue or None

            result['price'] = negotiated_rate or response.RatedShipment[0].TotalCharges.MonetaryValue
            return result

        except Fault as e:
            code = e.detail.xpath("//err:PrimaryErrorCode/err:Code", namespaces=self.ns)[0].text
            description = e.detail.xpath("//err:PrimaryErrorCode/err:Description", namespaces=self.ns)[0].text
            return self.get_error_message(code, description)
        except IOError as e:
            return self.get_error_message('0', 'UPS Server Not Found:\n%s' % e)