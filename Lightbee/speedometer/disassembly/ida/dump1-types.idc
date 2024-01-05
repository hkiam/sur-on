//
// +-------------------------------------------------------------------------+
// |      This file was generated by The Interactive Disassembler (IDA)      |
// |           Copyright (c) 2022 Hex-Rays, <support@hex-rays.com>           |
// |                      License info: 48-4174-32E0-0F                      |
// |                       Think-Cell Operations GmbH                        |
// +-------------------------------------------------------------------------+
//
//
//      This file contains the user-defined type definitions.
//      To use it press F2 in IDA and enter the name of this file.
//

#define UNLOADED_FILE   1
#include <idc.idc>

static main(void)
{
        Enums();              // enumerations
        Structures();         // structure types
        ApplyStrucTInfos();
	set_inf_attr(INF_LOW_OFF, 0x0);
	set_inf_attr(INF_HIGH_OFF, 0x100000);
}

static Enums_0(id) {

	id = add_enum(-1,"EOCDMode",0x1100000);
	set_enum_bf(id,1);
	add_enum_member(id,"ocd",	0X20,	0x20);
	return id;
}

//------------------------------------------------------------------------
// Information about enum types

static Enums(void) {
        auto id;
        begin_type_updating(UTP_ENUM);
	id = Enums_0(id);
        end_type_updating(UTP_ENUM);
}

static ApplyStrucTInfos_0(void) {
        auto id;
	id = get_struc_id("signature_data");
	id = get_struc_id("pfdl_request_t");
	id = get_struc_id("pfdl_descriptor_t");
	id = get_struc_id("maindispatcher_t");
	return id;
}

//------------------------------------------------------------------------
// Information about type information for structure members

static ApplyStrucTInfos() {
	ApplyStrucTInfos_0();
}

static Structures_0(id) {
        auto mid;

	id = add_struc(-1,"signature_data",0);
	id = add_struc(-1,"pfdl_request_t",0);
	id = add_struc(-1,"pfdl_descriptor_t",0);
	id = add_struc(-1,"maindispatcher_t",0);
	
	id = get_struc_id("signature_data");
	mid = add_struc_member(id,"device_code",	0,	0x000400,	-1,	3);
	mid = add_struc_member(id,"device_name",	0X3,	0x000400,	-1,	9);
	mid = add_struc_member(id,"field_C",	0XC,	0x000400,	-1,	3);
	mid = add_struc_member(id,"field_F",	0XF,	0x000400,	-1,	3);
	mid = add_struc_member(id,"field_12",	0X12,	0x000400,	-1,	3);
	
	id = get_struc_id("pfdl_request_t");
	mid = add_struc_member(id,"index_u16",	0,	0x10000400,	-1,	2);
	mid = add_struc_member(id,"data_pu08",	0X2,	0x10000400,	-1,	2);
	mid = add_struc_member(id,"bytecount_u16",	0X4,	0x10000400,	-1,	2);
	mid = add_struc_member(id,"command_enu",	0X6,	0x000400,	-1,	1);
	
	id = get_struc_id("pfdl_descriptor_t");
	mid = add_struc_member(id,"fx_MHz_u08",	0,	0x000400,	-1,	1);
	mid = add_struc_member(id,"wide_voltage_mode_u08",	0X1,	0x000400,	-1,	1);
	
	id = get_struc_id("maindispatcher_t");
	mid = add_struc_member(id,"counter",	0,	0x000400,	-1,	1);
	mid = add_struc_member(id,"field_1",	0X1,	0x000400,	-1,	1);
	mid = add_struc_member(id,"field_2",	0X2,	0x000400,	-1,	1);
	mid = add_struc_member(id,"field_3",	0X3,	0x000400,	-1,	1);
	mid = add_struc_member(id,"addr",	0X4,	0x10000400,	-1,	2);
	mid = add_struc_member(id,"cs",	0X6,	0x000400,	-1,	1);
	mid = add_struc_member(id,"field_7",	0X7,	0x000400,	-1,	1);
	return id;
}

//------------------------------------------------------------------------
// Information about structure types

static Structures(void) {
        auto id;
        begin_type_updating(UTP_STRUCT);
	id = Structures_0(id);
        end_type_updating(UTP_STRUCT);
}

// End of file.
